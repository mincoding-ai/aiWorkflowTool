"""
Session 2 코드 테스트: ClassExtractor + ClassInfo

전략:
- tmp_path에 Python 소스 파일을 직접 작성하여 실제 AST 파싱 검증
- SyntaxError 파일 스킵, 기반 클래스, 메서드 추출 등 경계 케이스 포함
"""

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.class_extractor import ClassExtractor, ClassInfo


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def extractor():
    return ClassExtractor()


@pytest.fixture
def project_dir(tmp_path):
    """클래스가 포함된 샘플 프로젝트"""
    (tmp_path / "models.py").write_text(
        "class Animal:\n"
        "    def speak(self):\n"
        "        pass\n"
        "\n"
        "class Dog(Animal):\n"
        "    def speak(self):\n"
        "        return 'Woof'\n"
        "    def fetch(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "utils.py").write_text(
        "def helper():\n"
        "    pass\n",
        encoding="utf-8",
    )
    return tmp_path


# ──────────────────────────────────────────────
# extract() 테스트
# ──────────────────────────────────────────────

class TestExtract:
    def test_클래스_개수_정확(self, extractor, project_dir):
        """models.py에서 2개 클래스를 추출해야 한다"""
        result = extractor.extract(project_dir)
        names = [r.name for r in result]
        assert "Animal" in names
        assert "Dog" in names

    def test_클래스_없는_파일은_결과_없음(self, extractor, project_dir):
        """utils.py에는 클래스가 없으므로 추가 ClassInfo가 없어야 한다"""
        result = extractor.extract(project_dir)
        names = [r.name for r in result]
        assert "helper" not in names  # 함수는 포함되지 않음

    def test_ai_analysis_제외(self, extractor, tmp_path):
        """_ai_analysis 폴더 내 파일은 탐색하지 않아야 한다"""
        ai_dir = tmp_path / "_ai_analysis"
        ai_dir.mkdir()
        (ai_dir / "output.py").write_text("class Hidden:\n    pass\n", encoding="utf-8")
        (tmp_path / "real.py").write_text("class Visible:\n    pass\n", encoding="utf-8")

        result = extractor.extract(tmp_path)
        names = [r.name for r in result]
        assert "Hidden" not in names
        assert "Visible" in names

    def test_syntax_error_파일_스킵(self, extractor, tmp_path):
        """SyntaxError가 있는 파일은 경고 후 스킵해야 한다"""
        (tmp_path / "bad.py").write_text("class Broken(\n    pass\n", encoding="utf-8")
        (tmp_path / "good.py").write_text("class Good:\n    pass\n", encoding="utf-8")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = extractor.extract(tmp_path)

        names = [r.name for r in result]
        assert "Good" in names
        assert "Broken" not in names
        assert any("SyntaxError" in str(warning.message) for warning in w)


# ──────────────────────────────────────────────
# ClassInfo 필드 검증
# ──────────────────────────────────────────────

class TestClassInfo:
    def test_메서드_목록_정확(self, extractor, project_dir):
        """Dog 클래스의 메서드가 정확히 추출되어야 한다"""
        result = extractor.extract(project_dir)
        dog = next(r for r in result if r.name == "Dog")
        assert "speak" in dog.methods
        assert "fetch" in dog.methods

    def test_기반_클래스_추출(self, extractor, project_dir):
        """Dog(Animal)의 기반 클래스가 Animal이어야 한다"""
        result = extractor.extract(project_dir)
        dog = next(r for r in result if r.name == "Dog")
        assert "Animal" in dog.base_classes

    def test_기반_클래스_없으면_빈_리스트(self, extractor, project_dir):
        """Animal은 기반 클래스가 없으므로 빈 리스트여야 한다"""
        result = extractor.extract(project_dir)
        animal = next(r for r in result if r.name == "Animal")
        assert animal.base_classes == []

    def test_소스코드_포함(self, extractor, project_dir):
        """source_code에 클래스 원본이 포함되어야 한다"""
        result = extractor.extract(project_dir)
        animal = next(r for r in result if r.name == "Animal")
        assert "class Animal" in animal.source_code
        assert "def speak" in animal.source_code

    def test_줄_번호_정확(self, extractor, tmp_path):
        """line_start가 실제 클래스 정의 줄 번호와 일치해야 한다"""
        src = "# 주석\n# 주석2\nclass MyClass:\n    pass\n"
        (tmp_path / "sample.py").write_text(src, encoding="utf-8")

        result = extractor.extract(tmp_path)
        assert result[0].line_start == 3

    def test_file_path_절대경로(self, extractor, project_dir):
        """file_path가 절대 경로여야 한다"""
        result = extractor.extract(project_dir)
        for info in result:
            assert Path(info.file_path).is_absolute()

    def test_다중_클래스_같은_파일(self, extractor, tmp_path):
        """같은 파일에 여러 클래스가 있을 때 모두 추출해야 한다"""
        src = (
            "class A:\n    pass\n\n"
            "class B:\n    pass\n\n"
            "class C:\n    pass\n"
        )
        (tmp_path / "multi.py").write_text(src, encoding="utf-8")
        result = extractor.extract(tmp_path)
        names = [r.name for r in result]
        assert set(names) == {"A", "B", "C"}


# ──────────────────────────────────────────────
# _extract_base_names() 직접 테스트
# ──────────────────────────────────────────────

class TestExtractBaseNames:
    def test_module_attribute_기반클래스(self, extractor, tmp_path):
        """module.Base 형태의 기반 클래스도 추출해야 한다"""
        src = "import base\nclass Child(base.Base):\n    pass\n"
        (tmp_path / "child.py").write_text(src, encoding="utf-8")
        result = extractor.extract(tmp_path)
        child = result[0]
        assert any("base.Base" in b or "Base" in b for b in child.base_classes)
