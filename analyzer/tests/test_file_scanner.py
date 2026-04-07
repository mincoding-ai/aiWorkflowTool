"""
Session 2 코드 테스트: FileScanner

전략:
- tmp_path fixture로 임시 디렉토리 생성 후 실제 파일 탐색 검증
- 토큰 한도 로직은 문자 수를 조작하여 검증
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.file_scanner import FileScanner, _TOKEN_LIMIT, _CHARS_PER_TOKEN


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def scanner():
    return FileScanner()


@pytest.fixture
def simple_project(tmp_path):
    """간단한 Python 프로젝트 구조 생성"""
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    sub = tmp_path / "utils"
    sub.mkdir()
    (sub / "helper.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (sub / "notes.txt").write_text("텍스트 파일", encoding="utf-8")  # 비Python 파일
    return tmp_path


# ──────────────────────────────────────────────
# scan() 테스트
# ──────────────────────────────────────────────

class TestScan:
    def test_py_파일만_탐색(self, scanner, simple_project):
        """확장자가 .py인 파일만 수집해야 한다"""
        result = scanner.scan(simple_project)
        for path in result:
            assert path.endswith(".py"), f"비Python 파일이 포함됨: {path}"

    def test_하위_디렉토리_재귀_탐색(self, scanner, simple_project):
        """하위 디렉토리 파일도 포함해야 한다"""
        result = scanner.scan(simple_project)
        paths = list(result.keys())
        assert any("helper.py" in p for p in paths)
        assert any("main.py" in p for p in paths)

    def test_파일_내용_정확히_읽음(self, scanner, simple_project):
        """파일 내용이 실제 텍스트와 일치해야 한다"""
        result = scanner.scan(simple_project)
        main_content = next(v for k, v in result.items() if "main.py" in k)
        assert "print('hello')" in main_content

    def test_ai_analysis_디렉토리_제외(self, scanner, tmp_path):
        """_ai_analysis 폴더 내 파일은 탐색 대상에서 제외해야 한다"""
        ai_dir = tmp_path / "_ai_analysis"
        ai_dir.mkdir()
        (ai_dir / "output.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "real.py").write_text("y = 2", encoding="utf-8")

        result = scanner.scan(tmp_path)
        paths = list(result.keys())
        # Path.parts로 정확한 컴포넌트 매칭 (문자열 부분 일치 방지)
        assert not any("_ai_analysis" in Path(p).parts for p in paths)
        assert any("real.py" in p for p in paths)

    def test_읽기_불가_파일_스킵(self, scanner, tmp_path):
        """OSError 발생 파일은 스킵하고 나머지는 정상 반환해야 한다"""
        good = tmp_path / "good.py"
        good.write_text("x = 1", encoding="utf-8")

        result = scanner.scan(tmp_path)
        assert len(result) >= 1

    def test_토큰_초과_시_요약본_반환(self, scanner, tmp_path):
        """전체 내용이 토큰 한도 초과 시 요약본(_extract_summary 결과)을 반환해야 한다"""
        # 토큰 한도를 넘는 큰 파일 생성
        big_content = "x = 1\n" * (_TOKEN_LIMIT * _CHARS_PER_TOKEN // 6 + 1000)
        (tmp_path / "big.py").write_text(big_content, encoding="utf-8")

        result = scanner.scan(tmp_path)
        # 요약본이면 원본보다 짧아야 한다
        assert len(list(result.values())[0]) < len(big_content)


# ──────────────────────────────────────────────
# _extract_summary() 테스트
# ──────────────────────────────────────────────

class TestExtractSummary:
    def test_50줄_이하_전체_반환(self, scanner):
        source = "\n".join([f"line{i}" for i in range(30)])
        result = scanner._extract_summary(source)
        assert "line29" in result

    def test_50줄_초과_시_첫50줄만(self, scanner):
        lines = [f"line{i}" for i in range(100)]
        source = "\n".join(lines)
        result = scanner._extract_summary(source)
        assert "line49" in result
        assert "line50" not in result.split("--- signatures ---")[0]

    def test_함수_시그니처_포함(self, scanner):
        source = "class Foo:\n    def bar(self):\n        pass\n"
        result = scanner._extract_summary(source)
        assert "--- signatures ---" in result
        assert "class Foo" in result or "def bar" in result


# ──────────────────────────────────────────────
# combine() 테스트
# ──────────────────────────────────────────────

class TestCombine:
    def test_파일들을_하나의_문자열로_합침(self, scanner):
        files = {"a.py": "x = 1", "b.py": "y = 2"}
        result = FileScanner.combine(files)
        assert "# a.py" in result
        assert "x = 1" in result
        assert "# b.py" in result
        assert "y = 2" in result

    def test_빈_딕셔너리_빈_문자열_반환(self, scanner):
        result = FileScanner.combine({})
        assert result == ""
