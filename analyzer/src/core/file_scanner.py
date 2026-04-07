# Design Ref: §5 Phase 1 — 소스 파일 탐색 및 내용 집계. 토큰 한도 초과 시 요약본 제공.

import ast
from pathlib import Path

# GPT-4o 입력 토큰 한도 (안전 마진 적용)
_TOKEN_LIMIT = 80_000
# 토큰 추정: 문자 수 / 4 (GPT 기준 평균)
_CHARS_PER_TOKEN = 4
# 토큰 초과 시 파일당 추출할 최대 줄 수
_SUMMARY_HEAD_LINES = 50

# 지원 언어별 확장자
SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".py",           # Python
    ".java",         # Java
    ".cpp", ".cc", ".cxx",  # C++
    ".c",            # C
    ".h", ".hpp",    # C/C++ 헤더
)


class FileScanner:
    """
    지정된 디렉토리에서 소스파일(Python/Java/C/C++)을 탐색하고 내용을 집계한다.
    전체 내용이 토큰 한도를 초과하면 각 파일의 요약본(첫 50줄 + 함수 시그니처)을 반환한다.
    """

    def __init__(self, extensions: tuple[str, ...] = SUPPORTED_EXTENSIONS) -> None:
        """
        Args:
            extensions: 탐색할 파일 확장자 목록 (기본값: Python/Java/C/C++ 전체)
        """
        self.extensions = extensions

    def scan(self, path: str | Path) -> dict[str, str]:
        """
        디렉토리를 재귀 탐색하여 소스파일 경로와 내용을 반환한다.
        토큰 한도 초과 시 get_summary()로 자동 전환한다.

        Args:
            path: 탐색할 디렉토리 경로

        Returns:
            {파일경로(str): 파일내용(str)} 딕셔너리.
            토큰 초과 시 요약본 내용이 담긴 딕셔너리 반환.
        """
        root = Path(path)
        files: dict[str, str] = {}

        for file_path in sorted(root.rglob("*")):
            if file_path.suffix not in self.extensions:
                continue
            # _ai_analysis 출력 디렉토리는 분석 대상에서 제외
            if "_ai_analysis" in file_path.parts:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                files[str(file_path)] = content
            except OSError:
                # 읽기 권한 없는 파일은 스킵
                continue

        # 토큰 추정치가 한도를 초과하면 요약본으로 교체
        total_chars = sum(len(v) for v in files.values())
        if total_chars // _CHARS_PER_TOKEN >= _TOKEN_LIMIT:
            return self._summarize(files)

        return files

    def get_summary(self, path: str | Path) -> dict[str, str]:
        """
        토큰 한도와 무관하게 항상 요약본을 반환한다.
        각 파일에서 첫 50줄과 함수·클래스 시그니처만 추출한다.

        Args:
            path: 탐색할 디렉토리 경로

        Returns:
            {파일경로: 요약 내용} 딕셔너리
        """
        files = self.scan.__wrapped__(self, path) if hasattr(self.scan, "__wrapped__") else {}
        root = Path(path)
        raw: dict[str, str] = {}

        for file_path in sorted(root.rglob("*")):
            if file_path.suffix not in self.extensions:
                continue
            if "_ai_analysis" in file_path.parts:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                raw[str(file_path)] = content
            except OSError:
                continue

        return self._summarize(raw)

    # ──────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────

    def _summarize(self, files: dict[str, str]) -> dict[str, str]:
        """
        각 파일에서 첫 N줄 + 함수·클래스 시그니처만 추출하여 반환한다.

        Args:
            files: {파일경로: 전체내용} 딕셔너리

        Returns:
            {파일경로: 요약내용} 딕셔너리
        """
        summarized: dict[str, str] = {}
        for file_path, content in files.items():
            summarized[file_path] = self._extract_summary(content)
        return summarized

    def _extract_summary(self, source: str) -> str:
        """
        단일 파일에서 첫 50줄과 함수·클래스 시그니처를 추출한다.

        Args:
            source: 소스파일 전체 내용

        Returns:
            요약 문자열 (첫 50줄 + "--- signatures ---" + 시그니처 목록)
        """
        lines = source.splitlines()
        head = "\n".join(lines[:_SUMMARY_HEAD_LINES])
        signatures = self._extract_signatures(source)

        if signatures:
            return f"{head}\n--- signatures ---\n{signatures}"
        return head

    def _extract_signatures(self, source: str) -> str:
        """
        AST를 파싱하여 클래스 정의와 함수 정의 시그니처를 추출한다.
        파싱 실패 시 빈 문자열을 반환한다.

        Args:
            source: 소스파일 전체 내용

        Returns:
            시그니처 목록 문자열 (줄바꿈으로 구분)
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ""

        lines = source.splitlines()
        sigs: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                # 해당 줄의 원본 텍스트를 시그니처로 사용
                line_idx = node.lineno - 1
                if 0 <= line_idx < len(lines):
                    sigs.append(lines[line_idx].rstrip())

        return "\n".join(sigs)

    @staticmethod
    def combine(files: dict[str, str]) -> str:
        """
        파일 딕셔너리를 하나의 문자열로 합친다 (AI 프롬프트 전달용).

        Args:
            files: {파일경로: 내용} 딕셔너리

        Returns:
            "# 파일경로\\n내용\\n\\n" 형태로 합친 문자열
        """
        parts: list[str] = []
        for path, content in files.items():
            parts.append(f"# {path}\n{content}")
        return "\n\n".join(parts)
