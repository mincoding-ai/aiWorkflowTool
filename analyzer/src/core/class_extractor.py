# Design Ref: §5 Phase 2 — 소스파일에서 클래스 추출. Python은 AST, Java/C++는 정규식 사용.

import ast
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

# Python 파일 확장자
_PYTHON_EXTS = {".py"}
# Java 파일 확장자
_JAVA_EXTS = {".java"}
# C/C++ 파일 확장자
_CPP_EXTS = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"}

# Java 클래스/인터페이스/열거형 선언 패턴
_JAVA_CLASS_RE = re.compile(
    r"(?:(?:public|private|protected|abstract|final|static)\s+)*"
    r"(?:class|interface|enum)\s+(\w+)"
)
# Java 메서드 선언 패턴 (반환형 메서드명(파라미터))
_JAVA_METHOD_RE = re.compile(
    r"(?:(?:public|private|protected|static|final|abstract|native|synchronized)\s+)+"
    r"[\w<>\[\]]+\s+(\w+)\s*\("
)
# C++ 클래스/구조체 선언 패턴
_CPP_CLASS_RE = re.compile(
    r"\b(?:class|struct)\s+(\w+)\s*(?:final\s*)?(?:[:,{])"
)
# C++ 함수/메서드 정의 패턴 (단순화: 반환형 이름(파라미터) {)
_CPP_METHOD_RE = re.compile(
    r"^\s*[\w:*&<>]+\s+(\w+)\s*\([^;]*\)\s*(?:const\s*)?(?:override\s*)?(?:noexcept\s*)?\{"
)


@dataclass
class ClassInfo:
    """
    단일 클래스에 대한 메타데이터와 소스코드를 보관하는 데이터 클래스.
    Phase 3(의존성 분석)과 Phase 4(주석 삽입)에서 공유된다.
    """

    name: str
    """클래스 이름"""

    file_path: str
    """소스파일 절대 경로"""

    line_start: int
    """클래스 정의 시작 줄 번호 (1-based)"""

    line_end: int
    """클래스 정의 끝 줄 번호 (1-based, 포함)"""

    methods: list[str] = field(default_factory=list)
    """직접 정의된 메서드 이름 목록 (상속 메서드 제외)"""

    base_classes: list[str] = field(default_factory=list)
    """기반 클래스 이름 목록"""

    source_code: str = ""
    """클래스 전체 소스코드 (원본 들여쓰기 포함)"""

    language: str = "python"
    """소스 언어: 'python' | 'java' | 'cpp'"""


class ClassExtractor:
    """
    지정된 디렉토리의 소스파일에서 클래스를 추출한다.
    Python은 AST 파싱, Java/C++는 정규식 기반 파싱을 사용한다.
    """

    def extract(self, path: str | Path) -> list[ClassInfo]:
        """
        디렉토리 내 모든 지원 소스파일에서 클래스를 추출한다.

        Args:
            path: 탐색할 디렉토리 경로

        Returns:
            ClassInfo 목록 (파일 경로 → 클래스 등장 순서로 정렬)
        """
        root = Path(path)
        results: list[ClassInfo] = []

        all_exts = _PYTHON_EXTS | _JAVA_EXTS | _CPP_EXTS
        for file_path in sorted(root.rglob("*")):
            if file_path.suffix not in all_exts:
                continue
            if "_ai_analysis" in file_path.parts:
                continue
            infos = self._parse_file(file_path)
            results.extend(infos)

        return results

    # ──────────────────────────────────────────────
    # Private — 파일 종류별 파싱 분기
    # ──────────────────────────────────────────────

    def _parse_file(self, file_path: Path) -> list[ClassInfo]:
        """파일 확장자에 따라 적절한 파서로 분기한다."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        ext = file_path.suffix.lower()
        if ext in _PYTHON_EXTS:
            return self._parse_python(file_path, source)
        elif ext in _JAVA_EXTS:
            return self._parse_java(file_path, source)
        elif ext in _CPP_EXTS:
            return self._parse_cpp(file_path, source)
        return []

    # ──────────────────────────────────────────────
    # Python — AST 기반
    # ──────────────────────────────────────────────

    def _parse_python(self, file_path: Path, source: str) -> list[ClassInfo]:
        """Python AST로 클래스를 추출한다."""
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            warnings.warn(
                f"[ClassExtractor] SyntaxError — 파일 스킵: {file_path} ({e})",
                stacklevel=2,
            )
            return []

        source_lines = source.splitlines()
        infos: list[ClassInfo] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            info = self._build_python_class_info(node, file_path, source_lines)
            infos.append(info)

        return infos

    def _build_python_class_info(
        self, node: ast.ClassDef, file_path: Path, source_lines: list[str]
    ) -> ClassInfo:
        methods = [
            n.name
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        base_classes = self._extract_python_base_names(node.bases)
        line_start = node.lineno
        line_end = self._find_python_class_end(node, source_lines)
        source_code = "\n".join(source_lines[line_start - 1 : line_end])

        return ClassInfo(
            name=node.name,
            file_path=str(file_path),
            line_start=line_start,
            line_end=line_end,
            methods=methods,
            base_classes=base_classes,
            source_code=source_code,
            language="python",
        )

    def _extract_python_base_names(self, bases: list[ast.expr]) -> list[str]:
        names: list[str] = []
        for base in bases:
            if isinstance(base, ast.Name):
                names.append(base.id)
            elif isinstance(base, ast.Attribute):
                names.append(f"{ast.unparse(base)}")
        return names

    def _find_python_class_end(self, node: ast.ClassDef, source_lines: list[str]) -> int:
        if hasattr(node, "end_lineno") and node.end_lineno is not None:
            return node.end_lineno
        class_indent = len(source_lines[node.lineno - 1]) - len(
            source_lines[node.lineno - 1].lstrip()
        )
        last_line = node.lineno
        for i in range(node.lineno, len(source_lines)):
            line = source_lines[i]
            stripped = line.lstrip()
            if stripped and (len(line) - len(stripped)) <= class_indent and i > node.lineno:
                break
            last_line = i + 1
        return last_line

    # ──────────────────────────────────────────────
    # Java — 정규식 기반
    # ──────────────────────────────────────────────

    def _parse_java(self, file_path: Path, source: str) -> list[ClassInfo]:
        """Java 소스에서 class/interface/enum을 정규식으로 추출한다."""
        lines = source.splitlines()
        infos: list[ClassInfo] = []

        for line_idx, line in enumerate(lines):
            m = _JAVA_CLASS_RE.search(line)
            if not m:
                continue

            class_name = m.group(1)
            line_start = line_idx + 1  # 1-based
            line_end = self._find_brace_end(lines, line_idx)
            source_code = "\n".join(lines[line_idx:line_end])
            methods = self._extract_java_methods(source_code)
            base_classes = self._extract_java_bases(line)

            infos.append(ClassInfo(
                name=class_name,
                file_path=str(file_path),
                line_start=line_start,
                line_end=line_end,
                methods=methods,
                base_classes=base_classes,
                source_code=source_code,
                language="java",
            ))

        return infos

    def _extract_java_bases(self, class_decl_line: str) -> list[str]:
        """extends/implements에서 기반 클래스·인터페이스명을 추출한다."""
        bases: list[str] = []
        ext_m = re.search(r"\bextends\s+([\w,\s<>]+?)(?:\s+implements|\s*\{|$)", class_decl_line)
        if ext_m:
            bases.extend(n.strip().split("<")[0] for n in ext_m.group(1).split(",") if n.strip())
        impl_m = re.search(r"\bimplements\s+([\w,\s<>]+?)(?:\s*\{|$)", class_decl_line)
        if impl_m:
            bases.extend(n.strip().split("<")[0] for n in impl_m.group(1).split(",") if n.strip())
        return bases

    def _extract_java_methods(self, class_source: str) -> list[str]:
        """Java 클래스 소스에서 메서드 이름을 추출한다."""
        return list(dict.fromkeys(  # 순서 유지 중복 제거
            m.group(1) for m in _JAVA_METHOD_RE.finditer(class_source)
        ))

    # ──────────────────────────────────────────────
    # C/C++ — 정규식 기반
    # ──────────────────────────────────────────────

    def _parse_cpp(self, file_path: Path, source: str) -> list[ClassInfo]:
        """C++ 소스에서 class/struct를 정규식으로 추출한다."""
        lines = source.splitlines()
        infos: list[ClassInfo] = []

        for line_idx, line in enumerate(lines):
            m = _CPP_CLASS_RE.search(line)
            if not m:
                continue

            class_name = m.group(1)
            # 키워드 충돌 제외 (if/for/while 등 이름이 단어 경계로 보호됨)
            if class_name in {"if", "for", "while", "switch", "else", "return"}:
                continue

            line_start = line_idx + 1
            line_end = self._find_brace_end(lines, line_idx)
            source_code = "\n".join(lines[line_idx:line_end])
            methods = self._extract_cpp_methods(source_code)

            infos.append(ClassInfo(
                name=class_name,
                file_path=str(file_path),
                line_start=line_start,
                line_end=line_end,
                methods=methods,
                base_classes=[],
                source_code=source_code,
                language="cpp",
            ))

        return infos

    def _extract_cpp_methods(self, class_source: str) -> list[str]:
        """C++ 클래스 소스에서 메서드 이름을 추출한다."""
        return list(dict.fromkeys(
            m.group(1) for m in _CPP_METHOD_RE.finditer(class_source)
        ))

    # ──────────────────────────────────────────────
    # 공통 유틸 — 중괄호 매칭
    # ──────────────────────────────────────────────

    def _find_brace_end(self, lines: list[str], start_idx: int) -> int:
        """
        start_idx 줄부터 중괄호 깊이를 추적하여 클래스 블록 끝 줄 번호(1-based)를 반환한다.

        Args:
            lines: 전체 소스 줄 목록
            start_idx: 클래스 선언 줄 인덱스 (0-based)

        Returns:
            클래스 끝 줄 번호 (1-based). 중괄호 불일치 시 파일 끝 반환.
        """
        depth = 0
        in_string = False
        string_char = ""
        started = False

        for i in range(start_idx, len(lines)):
            line = lines[i]
            j = 0
            while j < len(line):
                ch = line[j]
                # 문자열 내부 처리 (간이)
                if in_string:
                    if ch == "\\" :
                        j += 1  # 이스케이프 스킵
                    elif ch == string_char:
                        in_string = False
                elif ch in ('"', "'"):
                    in_string = True
                    string_char = ch
                elif line[j:j+2] == "//":
                    break  # 줄 주석 이후 무시
                elif ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
                    if started and depth == 0:
                        return i + 1  # 1-based
                j += 1

        return len(lines)  # 불일치 시 파일 끝
