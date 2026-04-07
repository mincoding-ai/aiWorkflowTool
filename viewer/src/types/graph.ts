// Design Ref: §3 — Analyzer graph.json 스키마와 1:1 대응

export interface GraphNode {
  id: string;       // 클래스명 (React Flow node id로도 사용)
  label: string;    // 한글 레이블
  purpose: string;  // 한 줄 목적 설명
}

export interface GraphEdge {
  source: string;   // 출발 node id
  target: string;   // 도착 node id
  relation: string; // 한글 관계 레이블
}

export interface GraphData {
  generated_at: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// CustomNode 내부 data 타입 (React Flow NodeProps용)
export interface CustomNodeData extends Record<string, unknown> {
  name: string;     // GraphNode.id
  label: string;    // GraphNode.label
  purpose: string;  // GraphNode.purpose (툴팁/패널용)
}

// CustomEdge 내부 data 타입
export interface CustomEdgeData extends Record<string, unknown> {
  relation: string;
  offset?: number;  // 병렬 엣지 분리용 수직 오프셋 (px), 기본 0
}
