// Design Ref: §5.6 — DetailPanel: 선택 노드 목적 전문 + 연결 엣지 목록
import { useMemo } from 'react'
import { GraphNode, GraphEdge } from '../types/graph'
import './DetailPanel.css'

interface DetailPanelProps {
  selectedNode: GraphNode | null;  // null = 노드 미선택
  allEdges: GraphEdge[];           // 전체 엣지 (연결 필터용)
}

export function DetailPanel({ selectedNode, allEdges }: DetailPanelProps) {
  // Design Ref: §5.6 — outgoing: source === node.id, incoming: target === node.id
  // useMemo로 불필요한 재필터링 방지 (selectedNode나 allEdges 변경 시에만 재계산)
  const outgoing = useMemo(
    () => selectedNode ? allEdges.filter(e => e.source === selectedNode.id) : [],
    [allEdges, selectedNode]
  )
  const incoming = useMemo(
    () => selectedNode ? allEdges.filter(e => e.target === selectedNode.id) : [],
    [allEdges, selectedNode]
  )

  if (!selectedNode) {
    return (
      <div className="dp-root">
        <p className="dp-hint">노드를 클릭하면<br />상세 정보가 표시됩니다.</p>
      </div>
    )
  }

  return (
    <div className="dp-root">
      <p className="dp-label">선택된 노드</p>
      <h2 className="dp-name">{selectedNode.id}</h2>
      <p className="dp-sublabel">{selectedNode.label}</p>

      <div className="dp-section">
        <p className="dp-section-title">목적</p>
        <p className="dp-purpose">{selectedNode.purpose}</p>
      </div>

      {(outgoing.length > 0 || incoming.length > 0) && (
        <div className="dp-section">
          <p className="dp-section-title">연결 관계</p>
          <ul className="dp-edges">
            {outgoing.map((e) => (
              <li key={`out-${e.source}-${e.target}-${e.relation}`} className="dp-edge-item">
                <span className="dp-edge-dir dp-edge-dir--out">→</span>
                <span className="dp-edge-target">{e.target}</span>
                <span className="dp-edge-relation">{e.relation}</span>
              </li>
            ))}
            {incoming.map((e) => (
              <li key={`in-${e.source}-${e.target}-${e.relation}`} className="dp-edge-item">
                <span className="dp-edge-dir dp-edge-dir--in">←</span>
                <span className="dp-edge-target">{e.source}</span>
                <span className="dp-edge-relation">{e.relation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
