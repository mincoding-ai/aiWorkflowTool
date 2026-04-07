# Design Ref: §9 (GraphGenerator) — analysis.md + 의존성 그래프 → graph.json (Node + Edge)

from datetime import datetime, timezone

from ..ai.client import AIClient


class GraphGenerator:
    """
    analysis.md 내용과 의존성 그래프를 기반으로 의미론적 그래프 데이터를 생성한다.
    AIClient를 통해 Node와 Edge를 추출하고 graph.json 스키마에 맞게 반환한다.
    """

    def __init__(self, ai: AIClient) -> None:
        """
        Args:
            ai: AIClient 인스턴스 (Node/Edge 추출에 사용)
        """
        self.ai = ai

    def generate(
        self,
        analysis: str,
        design: str,
        dep_graph: dict[str, list[str]],
    ) -> dict:
        """
        Node + Edge를 추출하여 graph.json 형식의 딕셔너리를 반환한다.

        Args:
            analysis: analysis.md 전체 내용 ("ClassName : 목적" 형식 줄 포함)
            design: DESIGN.md 전체 내용
            dep_graph: {클래스명: [의존 클래스명]} 딕셔너리

        Returns:
            {
                "generated_at": ISO8601 문자열,
                "nodes": [{"id": str, "label": str, "purpose": str}],
                "edges": [{"source": str, "target": str, "relation": str}],
            }
        """
        purpose_map = self._parse_analysis(analysis)

        raw_nodes: list[dict] = self.ai.extract_semantic_nodes(analysis, design)
        raw_edges: list[dict] = self.ai.extract_semantic_edges(raw_nodes, dep_graph)

        # Node 정규화: purpose_map으로 목적 보강
        nodes: list[dict] = []
        for node in raw_nodes:
            node_id = node.get("id", "")
            nodes.append(
                {
                    "id": node_id,
                    "label": node.get("label", node_id),
                    "purpose": node.get("purpose") or purpose_map.get(node_id, ""),
                }
            )

        edges = self._filter_valid_edges(nodes, raw_edges)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": nodes,
            "edges": edges,
        }

    # ──────────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────────

    def _parse_analysis(self, content: str) -> dict[str, str]:
        """
        analysis.md 내용에서 "ClassName : 목적" 형식 줄을 파싱한다.

        Args:
            content: analysis.md 전체 텍스트

        Returns:
            {클래스명: 목적} 딕셔너리
        """
        result: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " : " in line:
                parts = line.split(" : ", 1)
                name = parts[0].strip()
                purpose = parts[1].strip()
                if name:
                    result[name] = purpose
        return result

    def _filter_valid_edges(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[dict]:
        """
        Node 목록에 존재하지 않는 source 또는 target을 포함한 Edge를 제거한다.

        Args:
            nodes: 유효한 Node 딕셔너리 목록 (각 항목에 "id" 키 필수)
            edges: 필터링할 Edge 딕셔너리 목록 (각 항목에 "source", "target" 키 필수)

        Returns:
            유효한 Edge만 포함한 목록
        """
        valid_ids = {node.get("id") for node in nodes}
        return [
            edge for edge in edges
            if edge.get("source") in valid_ids and edge.get("target") in valid_ids
        ]
