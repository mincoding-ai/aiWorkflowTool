"""
Session 4 코드 테스트: CommentInjector

전략:
- tmp_path에 실제 .py 파일 생성 후 주석 삽입 검증
- 백업 파일 생성, 문법 오류 시 복구, 파일 위치별(앞/중간/끝) 경계 케이스 포함
"""

import ast
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.class_extractor import ClassInfo, ClassExtractor
from src.core.comment_injector import CommentInjector


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_info(name: str, file_path: str, line_start: int, line_end: int) -> ClassInfo:
    return ClassInfo(
        name=name,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        methods=[],
        base_classes=[],
        source_code="",
    )


@pytest.fixture
def injector():
    return CommentInjector()


# ──────────────────────────────────────────────
# _replace_class_range() 단위 테스트
# ──────────────────────────────────────────────

class TestReplaceClassRange:
    def test_중간_범위_교체(self, injector):
        content = "line1\nline2\nline3\nline4\nline5\n"
        result = injector._replace_class_range(content, 2, 3, "NEW2\nNEW3")
        assert result == "line1\nNEW2\nNEW3\nline4\nline5\n"

    def test_첫_줄부터_교체(self, injector):
        content = "class A:\n    pass\nother\n"
        result = injector._replace_class_range(content, 1, 2, "class A:\n    \"\"\"주석\"\"\"\n    pass")
        assert result.startswith("class A:")
        assert "주석" in result
        assert "other" in result

    def test_마지막_줄까지_교체(self, injector):
        content = "other\nclass B:\n    pass\n"
        result = injector._replace_class_range(content, 2, 3, "class B:\n    \"\"\"B\"\"\"\n    pass")
        assert "other" in result
        assert "B" in result

    def test_뉴라인_보존(self, injector):
        """원본이 \n으로 끝나면 결과도 \n으로 끝나야 한다"""
        content = "class A:\n    pass\n"
        result = injector._replace_class_range(content, 1, 2, "class A:\n    pass")
        assert result.endswith("\n")

    def test_뉴라인_없으면_추가_안함(self, injector):
        """원본이 \n 없이 끝나면 결과도 \n 없이 끝나야 한다"""
        content = "class A:\n    pass"
        result = injector._replace_class_range(content, 1, 2, "class A:\n    pass")
        assert not result.endswith("\n")

    def test_단일_줄_교체(self, injector):
        content = "a\nb\nc\n"
        result = injector._replace_class_range(content, 2, 2, "REPLACED")
        assert result == "a\nREPLACED\nc\n"


# ──────────────────────────────────────────────
# inject() 통합 테스트
# ──────────────────────────────────────────────

class TestInject:
    def _write_and_extract(self, tmp_path, source: str) -> tuple[Path, ClassInfo]:
        """파일 작성 후 ClassExtractor로 ClassInfo 추출"""
        f = tmp_path / "sample.py"
        f.write_text(source, encoding="utf-8")
        extractor = ClassExtractor()
        infos = extractor.extract(tmp_path)
        return f, infos[0]

    def test_주석_삽입_성공(self, injector, tmp_path):
        """올바른 주석 코드 삽입 후 파일에 반영되어야 한다"""
        source = "class Dog:\n    def speak(self):\n        pass\n"
        f, info = self._write_and_extract(tmp_path, source)

        commented = (
            'class Dog:\n'
            '    """개를 나타내는 클래스"""\n'
            '    def speak(self):\n'
            '        """짖는 소리를 반환한다"""\n'
            '        pass\n'
        )
        result = injector.inject(info, commented)

        assert result is True
        content = f.read_text(encoding="utf-8")
        assert "개를 나타내는 클래스" in content
        assert "짖는 소리를 반환한다" in content

    def test_백업_파일_생성(self, injector, tmp_path):
        """inject 후 .bak 파일이 생성되어야 한다"""
        source = "class Cat:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)

        injector.inject(info, "class Cat:\n    \"\"\"고양이\"\"\"\n    pass\n")
        bak = f.with_suffix(".py.bak")
        assert bak.exists()

    def test_백업_파일에_원본_내용(self, injector, tmp_path):
        """.bak 파일에 원본 내용이 그대로 보존되어야 한다"""
        source = "class Bird:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)

        injector.inject(info, "class Bird:\n    \"\"\"새\"\"\"\n    pass\n")
        bak = f.with_suffix(".py.bak")
        assert "class Bird" in bak.read_text(encoding="utf-8")
        assert "새" not in bak.read_text(encoding="utf-8")

    def test_문법_오류_시_원본_복구(self, injector, tmp_path):
        """주석 삽입 결과가 SyntaxError면 원본이 복구되어야 한다"""
        source = "class Fish:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)
        original = f.read_text(encoding="utf-8")

        broken = "class Fish(\n    # 깨진 코드\n"  # SyntaxError
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = injector.inject(info, broken)

        assert result is False
        assert f.read_text(encoding="utf-8") == original
        assert any("문법 오류" in str(warning.message) for warning in w)

    def test_문법_검증_통과하면_True(self, injector, tmp_path):
        """유효한 주석 코드 삽입 시 True를 반환해야 한다"""
        source = "class Lion:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)
        result = injector.inject(info, "class Lion:\n    \"\"\"사자\"\"\"\n    pass\n")
        assert result is True

    def test_파일_끝_클래스_처리(self, injector, tmp_path):
        """파일 마지막 클래스도 정상 처리되어야 한다"""
        source = "x = 1\n\nclass Last:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)
        last_info = next(i for i in ClassExtractor().extract(tmp_path) if i.name == "Last")

        result = injector.inject(last_info, "class Last:\n    \"\"\"마지막\"\"\"\n    pass\n")
        assert result is True
        assert "x = 1" in f.read_text(encoding="utf-8")

    def test_파일_시작_클래스_처리(self, injector, tmp_path):
        """파일 첫 줄 클래스도 정상 처리되어야 한다"""
        source = "class First:\n    pass\n\nx = 1\n"
        f, info = self._write_and_extract(tmp_path, source)

        result = injector.inject(info, "class First:\n    \"\"\"첫번째\"\"\"\n    pass\n")
        assert result is True
        content = f.read_text(encoding="utf-8")
        assert "x = 1" in content
        assert "첫번째" in content

    def test_재주입_시_백업_중복_생성_안함(self, injector, tmp_path):
        """이미 .bak이 있으면 덮어쓰지 않아야 한다 (최초 원본 보존)"""
        source = "class Repeat:\n    pass\n"
        f, info = self._write_and_extract(tmp_path, source)

        injector.inject(info, "class Repeat:\n    \"\"\"1차\"\"\"\n    pass\n")
        bak_content_first = f.with_suffix(".py.bak").read_text(encoding="utf-8")

        # 두 번째 주입
        info2 = ClassExtractor().extract(tmp_path)[0]
        injector.inject(info2, "class Repeat:\n    \"\"\"2차\"\"\"\n    pass\n")
        bak_content_second = f.with_suffix(".py.bak").read_text(encoding="utf-8")

        # 백업은 최초 원본이어야 함
        assert bak_content_first == bak_content_second
        assert "pass" in bak_content_first  # 주석 없는 원본


# ──────────────────────────────────────────────
# _verify_syntax() 단위 테스트
# ──────────────────────────────────────────────

class TestVerifySyntax:
    def test_유효한_코드(self, injector):
        assert injector._verify_syntax("class A:\n    pass\n", "test.py") is True

    def test_깨진_코드(self, injector):
        assert injector._verify_syntax("class A(\n    pass", "test.py") is False

    def test_빈_문자열(self, injector):
        assert injector._verify_syntax("", "test.py") is True

    def test_비파이썬_파일은_항상_True(self, injector):
        """Java/C++ 파일은 AST 검증 없이 항상 True 반환"""
        assert injector._verify_syntax("class A(\n    pass", "Broken.java") is True
        assert injector._verify_syntax("class A(\n    pass", "broken.cpp") is True
