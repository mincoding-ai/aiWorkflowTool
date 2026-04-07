"""
Session 6 코드 테스트: GraphGenerator

전략:
- AIClient Mock으로 실제 API 호출 없이 전체 흐름 검증
- _parse_analysis: 정상/빈/잘못된 형식 파싱 정확도
- generate(): 반환 스키마 (nodes/edges/generated_at 키) 검증
- _filter_valid_edges(): 유효하지 않은 source/target 제거
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.graph_generator import GraphGenerator


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_ai():
    ai = MagicMock()
    ai.extract_semantic_nodes.return_value = [
        {"id": "Alpha", "label": "Alpha", "purpose": "알파 클래스"},
        {"id": "Beta", "label": "Beta", "purpose": "베타 클래스"},
    ]
    ai.extract_semantic_edges.return_value = [
        {"source": "Alpha", "target": "Beta", "relation": "사용한다"},
    ]
    return ai


@pytest.fixture
def gen(mock_ai):
    return GraphGenerator(ai=mock_ai)


# ──────────────────────────────────────────────
# _parse_analysis()
# ──────────────────────────────────────────────

class TestParseAnalysis:
    def test_정상_파싱(self, gen):
        content = "# analysis.md\n\nAlpha : 알파 목적\nBeta : 베타 목적\n"
        result = gen._parse_analysis(content)
        assert result == {"Alpha": "알파 목적", "Beta": "베타 목적"}

    def test_빈_문자열(self, gen):
        assert gen._parse_analysis("") == {}

    def test_헤더만_있는_경우(self, gen):
        content = "# analysis.md\n\n"
        assert gen._parse_analysis(content) == {}

    def test_잘못된_형식_줄_무시(self, gen):
        content = "AlphaWithoutColon\nBeta : 베타 목적\n"
        result = gen._parse_analysis(content)
        assert "AlphaWithoutColon" not in result
        assert result["Beta"] == "베타 목적"

    def test_콜론_포함_목적_문자열(self, gen):
        """목적에 ' : ' 가 포함되어 있어도 첫 번째 분리만 수행해야 한다"""
        content = "MyClass : 목적: 세부 내용\n"
        result = gen._parse_analysis(content)
        assert result["MyClass"] == "목적: 세부 내용"

    def test_공백_줄_무시(self, gen):
        content = "\n   \nAlpha : 알파\n\n"
        result = gen._parse_analysis(content)
        assert result == {"Alpha": "알파"}

    def test_여러_클래스(self, gen):
        lines = [f"Class{i} : 목적{i}" for i in range(10)]
        content = "\n".join(lines)
        result = gen._parse_analysis(content)
        assert len(result) == 10
        assert result["Class5"] == "목적5"


# ──────────────────────────────────────────────
# _filter_valid_edges()
# ──────────────────────────────────────────────

class TestFilterValidEdges:
    def test_유효한_엣지_통과(self, gen):
        nodes = [{"id": "A"}, {"id": "B"}]
        edges = [{"source": "A", "target": "B", "relation": "사용"}]
        result = gen._filter_valid_edges(nodes, edges)
        assert len(result) == 1

    def test_유효하지_않은_source_제거(self, gen):
        nodes = [{"id": "A"}, {"id": "B"}]
        edges = [{"source": "UNKNOWN", "target": "B", "relation": "사용"}]
        result = gen._filter_valid_edges(nodes, edges)
        assert len(result) == 0

    def test_유효하지_않은_target_제거(self, gen):
        nodes = [{"id": "A"}, {"id": "B"}]
        edges = [{"source": "A", "target": "UNKNOWN", "relation": "사용"}]
        result = gen._filter_valid_edges(nodes, edges)
        assert len(result) == 0

    def test_빈_nodes(self, gen):
        edges = [{"source": "A", "target": "B", "relation": "사용"}]
        result = gen._filter_valid_edges([], edges)
        assert result == []

    def test_빈_edges(self, gen):
        nodes = [{"id": "A"}]
        result = gen._filter_valid_edges(nodes, [])
        assert result == []

    def test_혼합_유효_무효(self, gen):
        nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        edges = [
            {"source": "A", "target": "B", "relation": "사용"},
            {"source": "A", "target": "MISSING", "relation": "사용"},
            {"source": "B", "target": "C", "relation": "포함"},
        ]
        result = gen._filter_valid_edges(nodes, edges)
        assert len(result) == 2
        targets = [e["target"] for e in result]
        assert "MISSING" not in targets


# ──────────────────────────────────────────────
# generate() — 스키마 + 전체 흐름
# ──────────────────────────────────────────────

class TestGenerate:
    def test_반환_스키마_키_존재(self, gen):
        result = gen.generate("Alpha : 알파\nBeta : 베타", "DESIGN", {"Alpha": ["Beta"]})
        assert "generated_at" in result
        assert "nodes" in result
        assert "edges" in result

    def test_nodes_구조(self, gen):
        result = gen.generate("Alpha : 알파\nBeta : 베타", "DESIGN", {})
        for node in result["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "purpose" in node

    def test_edges_구조(self, gen):
        result = gen.generate("Alpha : 알파\nBeta : 베타", "DESIGN", {"Alpha": ["Beta"]})
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge

    def test_generated_at_iso형식(self, gen):
        result = gen.generate("", "", {})
        from datetime import datetime, timezone
        # ISO8601 파싱 가능해야 함
        dt = datetime.fromisoformat(result["generated_at"])
        assert dt.tzinfo is not None

    def test_purpose_map으로_보강(self, mock_ai):
        """AI 반환 node에 purpose가 없으면 analysis.md에서 보강해야 한다"""
        mock_ai.extract_semantic_nodes.return_value = [
            {"id": "Alpha", "label": "Alpha", "purpose": ""},  # 빈 목적
        ]
        mock_ai.extract_semantic_edges.return_value = []
        gen = GraphGenerator(ai=mock_ai)

        analysis = "Alpha : analysis에서 온 목적\n"
        result = gen.generate(analysis, "", {})
        assert result["nodes"][0]["purpose"] == "analysis에서 온 목적"

    def test_ai_purpose_우선(self, mock_ai):
        """AI 반환 node에 purpose가 있으면 analysis.md 값보다 우선해야 한다"""
        mock_ai.extract_semantic_nodes.return_value = [
            {"id": "Alpha", "label": "Alpha", "purpose": "AI가 준 목적"},
        ]
        mock_ai.extract_semantic_edges.return_value = []
        gen = GraphGenerator(ai=mock_ai)

        analysis = "Alpha : analysis 목적\n"
        result = gen.generate(analysis, "", {})
        assert result["nodes"][0]["purpose"] == "AI가 준 목적"

    def test_유효하지_않은_edge_필터링(self, mock_ai):
        """generate()가 _filter_valid_edges를 통해 invalid edge를 제거해야 한다"""
        mock_ai.extract_semantic_nodes.return_value = [
            {"id": "Alpha", "label": "Alpha", "purpose": "알파"},
        ]
        mock_ai.extract_semantic_edges.return_value = [
            {"source": "Alpha", "target": "NONEXISTENT", "relation": "사용"},
            {"source": "Alpha", "target": "Alpha", "relation": "자기참조"},
        ]
        gen = GraphGenerator(ai=mock_ai)
        result = gen.generate("Alpha : 알파", "", {})
        # NONEXISTENT는 제거, 자기참조(Alpha→Alpha)는 유효
        targets = [e["target"] for e in result["edges"]]
        assert "NONEXISTENT" not in targets

    def test_빈_analysis_빈_graph(self, mock_ai):
        mock_ai.extract_semantic_nodes.return_value = []
        mock_ai.extract_semantic_edges.return_value = []
        gen = GraphGenerator(ai=mock_ai)
        result = gen.generate("", "", {})
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_ai_client_호출됨(self, gen, mock_ai):
        gen.generate("Alpha : 알파", "DESIGN", {"Alpha": []})
        mock_ai.extract_semantic_nodes.assert_called_once()
        mock_ai.extract_semantic_edges.assert_called_once()
