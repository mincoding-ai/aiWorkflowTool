"""
Session 3 코드 테스트: DependencyAnalyzer

전략:
- ClassInfo를 직접 생성하여 의존성 그래프 구성 검증
- 위상 정렬 순서 (단순 → 복잡) 검증
- 순환 의존성 경고 + 전체 포함 보장
- verify() 누락 감지 검증
"""

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.class_extractor import ClassInfo
from src.core.dependency_analyzer import DependencyAnalyzer


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_class(name: str, source: str = "") -> ClassInfo:
    """테스트용 ClassInfo 생성 헬퍼"""
    return ClassInfo(
        name=name,
        file_path=f"/fake/{name}.py",
        line_start=1,
        line_end=10,
        methods=[],
        base_classes=[],
        source_code=source or f"class {name}:\n    pass\n",
    )


@pytest.fixture
def analyzer():
    return DependencyAnalyzer()


# ──────────────────────────────────────────────
# build_graph() 테스트
# ──────────────────────────────────────────────

class TestBuildGraph:
    def test_의존성_없는_클래스_빈_리스트(self, analyzer):
        """다른 클래스를 참조하지 않으면 빈 의존성 리스트를 반환해야 한다"""
        classes = [make_class("A"), make_class("B")]
        graph = analyzer.build_graph(classes)
        assert graph["A"] == []
        assert graph["B"] == []

    def test_단순_의존성_감지(self, analyzer):
        """A의 소스코드에 B가 등장하면 A → B 의존성이 생성되어야 한다"""
        b = make_class("B")
        a = make_class("A", "class A:\n    def method(self):\n        x = B()\n")
        classes = [a, b]
        graph = analyzer.build_graph(classes)
        assert "B" in graph["A"]
        assert graph["B"] == []

    def test_자기_자신_참조_제외(self, analyzer):
        """클래스 자신의 이름은 의존성에 포함되지 않아야 한다"""
        a = make_class("A", "class A:\n    def method(self):\n        return A()\n")
        graph = analyzer.build_graph([a])
        assert "A" not in graph["A"]

    def test_알려지지_않은_클래스_제외(self, analyzer):
        """분석 대상이 아닌 외부 클래스 참조는 의존성에 포함되지 않아야 한다"""
        a = make_class("A", "class A:\n    def method(self):\n        x = ExternalLib()\n")
        graph = analyzer.build_graph([a])
        assert "ExternalLib" not in graph["A"]

    def test_다중_의존성(self, analyzer):
        """A가 B와 C를 모두 참조하면 둘 다 의존성에 포함되어야 한다"""
        b = make_class("B")
        c = make_class("C")
        a = make_class("A", "class A:\n    def m(self):\n        B()\n        C()\n")
        graph = analyzer.build_graph([a, b, c])
        assert "B" in graph["A"]
        assert "C" in graph["A"]

    def test_attribute_참조_감지(self, analyzer):
        """module.ClassName 형태의 참조도 감지해야 한다"""
        b = make_class("B")
        a = make_class("A", "class A:\n    def m(self):\n        module.B()\n")
        graph = analyzer.build_graph([a, b])
        assert "B" in graph["A"]


# ──────────────────────────────────────────────
# sort() 테스트
# ──────────────────────────────────────────────

class TestSort:
    def test_단순_선후_관계(self, analyzer):
        """A→B 의존 시 B(단순)가 A(복잡) 앞에 와야 한다"""
        b = make_class("B")
        a = make_class("A", "class A:\n    def m(self):\n        B()\n")
        result = analyzer.sort([a, b])
        names = [cls.name for cls in result]
        assert names.index("B") < names.index("A")

    def test_다단_의존성_정렬(self, analyzer):
        """A→B→C 의존 시 순서는 C, B, A 여야 한다"""
        c = make_class("C")
        b = make_class("B", "class B:\n    def m(self):\n        C()\n")
        a = make_class("A", "class A:\n    def m(self):\n        B()\n")
        result = analyzer.sort([a, b, c])
        names = [cls.name for cls in result]
        assert names.index("C") < names.index("B") < names.index("A")

    def test_독립_클래스_모두_포함(self, analyzer):
        """의존성 없는 클래스들도 결과에 모두 포함되어야 한다"""
        classes = [make_class("X"), make_class("Y"), make_class("Z")]
        result = analyzer.sort(classes)
        assert {cls.name for cls in result} == {"X", "Y", "Z"}

    def test_전체_개수_보존(self, analyzer):
        """정렬 결과의 클래스 수는 입력과 동일해야 한다"""
        b = make_class("B")
        a = make_class("A", "class A:\n    def m(self):\n        B()\n")
        result = analyzer.sort([a, b])
        assert len(result) == 2

    def test_순환_의존성_경고_후_전체_포함(self, analyzer):
        """A→B, B→A 순환 의존성에서 경고를 발생시키고 모든 클래스를 포함해야 한다"""
        a = make_class("A", "class A:\n    def m(self):\n        B()\n")
        b = make_class("B", "class B:\n    def m(self):\n        A()\n")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = analyzer.sort([a, b])

        names = {cls.name for cls in result}
        assert names == {"A", "B"}
        assert any("순환" in str(warning.message) for warning in w)

    def test_빈_목록_입력(self, analyzer):
        """빈 목록 입력 시 빈 목록을 반환해야 한다"""
        assert analyzer.sort([]) == []

    def test_단일_클래스(self, analyzer):
        """클래스가 1개일 때도 정상 동작해야 한다"""
        result = analyzer.sort([make_class("Solo")])
        assert len(result) == 1
        assert result[0].name == "Solo"


# ──────────────────────────────────────────────
# verify() 테스트
# ──────────────────────────────────────────────

class TestVerify:
    def test_전체_포함_시_빈_리스트(self, analyzer):
        """모든 클래스가 정렬 결과에 포함되면 빈 리스트를 반환해야 한다"""
        classes = [make_class("A"), make_class("B")]
        ordered = list(classes)
        assert analyzer.verify(classes, ordered) == []

    def test_누락_클래스_감지(self, analyzer):
        """정렬 결과에 없는 클래스명이 반환되어야 한다"""
        original = [make_class("A"), make_class("B"), make_class("C")]
        ordered = [make_class("A"), make_class("B")]  # C 누락
        missing = analyzer.verify(original, ordered)
        assert "C" in missing

    def test_누락_없으면_빈_리스트(self, analyzer):
        """누락이 없으면 빈 리스트여야 한다"""
        cls = make_class("OnlyOne")
        assert analyzer.verify([cls], [cls]) == []

    def test_빈_원본_빈_결과(self, analyzer):
        """원본이 비어있으면 누락도 없어야 한다"""
        assert analyzer.verify([], []) == []


# ──────────────────────────────────────────────
# _find_references() 테스트
# ──────────────────────────────────────────────

class TestFindReferences:
    def test_name_참조(self, analyzer):
        source = "class A:\n    def m(self):\n        x = MyClass()\n"
        result = analyzer._find_references(source, {"MyClass", "Other"})
        assert "MyClass" in result

    def test_attribute_참조(self, analyzer):
        source = "class A:\n    def m(self):\n        m.MyClass()\n"
        result = analyzer._find_references(source, {"MyClass"})
        assert "MyClass" in result

    def test_없는_클래스_미포함(self, analyzer):
        source = "class A:\n    def m(self):\n        x = 1\n"
        result = analyzer._find_references(source, {"Ghost"})
        assert "Ghost" not in result

    def test_빈_소스코드(self, analyzer):
        assert analyzer._find_references("", {"A"}) == set()

    def test_syntax_error_빈_셋(self, analyzer):
        result = analyzer._find_references("class Broken(\n    pass", {"A"})
        assert result == set()
