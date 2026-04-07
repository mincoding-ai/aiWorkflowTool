# Design Ref: §5 Phase 4 — 클래스 단위 주석 삽입. 원본 백업 후 교체, 문법 오류 시 자동 복구.

import ast
import shutil
import warnings
from pathlib import Path

from .class_extractor import ClassInfo


class CommentInjector:
    """
    AI가 생성한 주석 포함 클래스 소스코드를 원본 파일에 삽입한다.
    삽입 전 .bak 백업을 생성하고, 삽입 후 문법 오류가 발생하면 백업으로 복구한다.
    """

    def inject(self, class_info: ClassInfo, commented_source: str) -> bool:
        """
        단일 클래스에 주석을 삽입한다.

        Args:
            class_info: 삽입 대상 클래스의 메타데이터 (파일 경로, 줄 번호 포함)
            commented_source: AI가 생성한 주석 달린 클래스 소스코드 전문

        Returns:
            True: 삽입 성공 / False: 삽입 실패 (원본 복구됨)
        """
        file_path = Path(class_info.file_path)
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")

        original_content = file_path.read_text(encoding="utf-8")
        self._backup(file_path, backup_path)

        new_content = self._replace_class_range(
            original_content,
            class_info.line_start,
            class_info.line_end,
            commented_source,
        )
        file_path.write_text(new_content, encoding="utf-8")

        if not self._verify_syntax(new_content, str(file_path)):
            # 문법 오류: 백업에서 복구
            self._restore(file_path, backup_path)
            warnings.warn(
                f"[CommentInjector] 문법 오류 — 원본 복구: {file_path} "
                f"(클래스: {class_info.name})",
                stacklevel=2,
            )
            return False

        return True

    def inject_many(
        self, pairs: list[tuple[ClassInfo, str]]
    ) -> dict[str, bool]:
        """
        같은 파일 내 여러 클래스를 순서대로 삽입한다.
        파일당 백업은 최초 1회만 생성하며, 어느 클래스에서 실패해도 해당 파일은 복구된다.

        Args:
            pairs: (ClassInfo, commented_source) 튜플 목록.
                   반드시 line_start 내림차순으로 정렬되어야 한다 (아래→위로 교체).

        Returns:
            {클래스명: 성공여부} 딕셔너리
        """
        # 파일별로 그룹화
        by_file: dict[str, list[tuple[ClassInfo, str]]] = {}
        for info, src in pairs:
            by_file.setdefault(info.file_path, []).append((info, src))

        results: dict[str, bool] = {}

        for file_path_str, file_pairs in by_file.items():
            file_path = Path(file_path_str)
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            self._backup(file_path, backup_path)

            # 아래→위 순서로 교체해야 줄 번호가 어긋나지 않는다
            sorted_pairs = sorted(
                file_pairs, key=lambda p: p[0].line_start, reverse=True
            )

            ok = True
            for info, commented_src in sorted_pairs:
                content = file_path.read_text(encoding="utf-8")
                new_content = self._replace_class_range(
                    content,
                    info.line_start,
                    info.line_end,
                    commented_src,
                )
                file_path.write_text(new_content, encoding="utf-8")

                if not self._verify_syntax(new_content, file_path_str):
                    warnings.warn(
                        f"[CommentInjector] 문법 오류 — 파일 전체 복구: {file_path} "
                        f"(클래스: {info.name})",
                        stacklevel=2,
                    )
                    self._restore(file_path, backup_path)
                    # 이 파일의 나머지 클래스도 실패 처리
                    for fi, _ in file_pairs:
                        results[fi.name] = False
                    ok = False
                    break
                results[info.name] = True

        return results

    # ──────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────

    def _replace_class_range(
        self,
        content: str,
        line_start: int,
        line_end: int,
        replacement: str,
    ) -> str:
        """
        파일 내용에서 line_start~line_end(1-based, 포함) 범위를 replacement로 교체한다.

        Args:
            content: 원본 파일 전체 내용
            line_start: 교체 시작 줄 번호 (1-based)
            line_end: 교체 끝 줄 번호 (1-based, 포함)
            replacement: 교체할 텍스트

        Returns:
            교체된 파일 전체 내용
        """
        ends_with_newline = content.endswith("\n")
        lines = content.splitlines()

        before = lines[: line_start - 1]
        after = lines[line_end:]  # line_end는 포함이므로 +1 인덱스부터
        replacement_lines = replacement.splitlines()

        merged = before + replacement_lines + after
        result = "\n".join(merged)

        if ends_with_newline:
            result += "\n"

        return result

    def _backup(self, file_path: Path, backup_path: Path) -> None:
        """
        원본 파일을 .bak으로 복사한다. 이미 백업이 있으면 덮어쓰지 않는다.

        Args:
            file_path: 원본 파일 경로
            backup_path: 백업 저장 경로
        """
        if not backup_path.exists():
            shutil.copy2(file_path, backup_path)

    def _restore(self, file_path: Path, backup_path: Path) -> None:
        """
        백업 파일로 원본을 복구한다.

        Args:
            file_path: 복구할 파일 경로
            backup_path: 복구 원본(.bak) 경로
        """
        if backup_path.exists():
            shutil.copy2(backup_path, file_path)

    def _verify_syntax(self, content: str, filename: str = "<unknown>") -> bool:
        """
        파일 내용의 문법을 검사한다.
        Python(.py)만 AST로 검증하고, Java/C++ 등은 항상 True를 반환한다.

        Args:
            content: 검사할 파일 내용
            filename: 오류 메시지용 파일명 (확장자로 언어 판별)

        Returns:
            True: 문법 정상(또는 비Python) / False: Python SyntaxError 발생
        """
        if not filename.endswith(".py"):
            return True  # 비Python 파일은 AST 검증 불가 → 삽입 결과 신뢰
        try:
            ast.parse(content, filename=filename)
            return True
        except SyntaxError:
            return False
