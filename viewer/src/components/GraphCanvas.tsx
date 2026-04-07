// Design Ref: §5.3 — GraphCanvas: React Flow 캔버스 래퍼
// 색상 계산을 렌더 인라인(useMemo)으로 처리해 노드 클릭 → 1회 렌더만 발생하도록 최적화
import { useEffect, useMemo, useCallback } from 'react'
import {
  ReactFlow, MiniMap, Controls, Background, BackgroundVariant,
  Node, Edge, useNodesState, useEdgesState, MarkerType,
} from '@xyflow/react'
import { CustomNodeData, CustomEdgeData } from '../types/graph'
import { CustomNode } from './CustomNode'
import { CustomEdge } from './CustomEdge'

// 색상 상수 (App.tsx에서 이동 — 노드 선택 색상과 DetailPanel 색상 동일하게 유지)
const COLOR_OUTGOING = '#4F6EF7'
const COLOR_INCOMING = '#10b981'
const COLOR_DEFAULT  = '#94a3b8'
const COLOR_DIMMED   = '#e2e8f0'

interface GraphCanvasProps {
  nodes: Node<CustomNodeData>[];
  edges: Edge<CustomEdgeData>[];       // 구조 전용 base 엣지 (색상 없음)
  selectedNodeId: string | null;       // 색상 계산에만 사용 — prop 변경 시 useEffect 없이 즉시 반영
  onNodeClick: (nodeId: string) => void;
}

const nodeTypes = { customNode: CustomNode }
const edgeTypes = { customEdge: CustomEdge }

export function GraphCanvas({ nodes: propNodes, edges: propEdges, selectedNodeId, onNodeClick }: GraphCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(propNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(propEdges)

  // 새 graph.json 로드 시 노드 초기화
  useEffect(() => { setNodes(propNodes) }, [propNodes, setNodes])

  // 엣지 구조 동기화: 새 파일 로드 시에만 발동 (propEdges는 선택 변경 시 불변)
  // O(n) Map 룩업, offset 보존
  useEffect(() => {
    setEdges(prev => {
      const prevById = new Map(prev.map(e => [e.id, e]))
      const sameGraph =
        prev.length === propEdges.length &&
        propEdges.every(pe => prevById.has(pe.id))

      if (!sameGraph) return propEdges  // 새 파일 로드

      // 같은 그래프 — 드래그된 offset만 보존, 나머지는 propEdges 기준
      return propEdges.map(pe => {
        const existing = prevById.get(pe.id)
        if (!existing) return pe
        const existingOffset = (existing.data as CustomEdgeData | undefined)?.offset
        const peOffset = (pe.data as CustomEdgeData | undefined)?.offset ?? 0
        return {
          ...pe,
          data: { ...pe.data, offset: existingOffset ?? peOffset } as CustomEdgeData,
        }
      })
    })
  }, [propEdges, setEdges])

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => onNodeClick(node.id),
    [onNodeClick]
  )

  // 색상 인라인 계산 — selectedNodeId 변경 시 useEffect/setEdges 없이 렌더 중 즉시 반영
  // 클릭 → 1회 렌더로 색상 반영 (이전: 2회 렌더)
  const displayEdges = useMemo((): Edge<CustomEdgeData>[] =>
    edges.map(e => {
      const stroke = !selectedNodeId      ? COLOR_DEFAULT
        : e.source === selectedNodeId    ? COLOR_OUTGOING
        : e.target === selectedNodeId    ? COLOR_INCOMING
        :                                  COLOR_DIMMED
      return {
        ...e,
        style: { stroke, strokeWidth: 1.8 },
        markerEnd: { type: MarkerType.Arrow, color: stroke, width: 20, height: 20, strokeWidth: 1.5 },
      }
    }),
  [edges, selectedNodeId])

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={displayEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
      >
        <MiniMap />
        <Controls />
        <Background variant={BackgroundVariant.Dots} gap={16} />
      </ReactFlow>
    </div>
  )
}
