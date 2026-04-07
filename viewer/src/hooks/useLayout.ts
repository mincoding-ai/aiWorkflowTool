// Design Ref: §4.2 — useLayout: dagre 계층형 레이아웃 계산 훅
import { useMemo } from 'react'
import { Node, Edge } from '@xyflow/react'
import dagre from 'dagre'
import { GraphData, CustomNodeData, CustomEdgeData } from '../types/graph'

const NODE_WIDTH = 200  // Design Ref: §4.2
const NODE_HEIGHT = 70

interface UseLayoutReturn {
  rfNodes: Node<CustomNodeData>[];
  rfEdges: Edge<CustomEdgeData>[];
}

export function useLayout(graphData: GraphData | null): UseLayoutReturn {
  return useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) {
      return { rfNodes: [], rfEdges: [] }
    }

    // dagre 그래프 초기화
    const g = new dagre.graphlib.Graph()
    g.setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 40 })

    // 노드 등록
    graphData.nodes.forEach(n => {
      g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
    })

    // 엣지 등록
    graphData.edges.forEach((e, i) => {
      // source/target이 실제 노드로 존재하는 경우만 추가 (방어)
      if (g.hasNode(e.source) && g.hasNode(e.target)) {
        g.setEdge(e.source, e.target, { id: `e${i}` })
      }
    })

    // 레이아웃 계산
    dagre.layout(g)

    // dagre 결과 → React Flow 노드 (중앙 기준 → 좌상단 기준 변환)
    const rfNodes: Node<CustomNodeData>[] = graphData.nodes.map(n => {
      const { x, y } = g.node(n.id)
      return {
        id: n.id,
        type: 'customNode',
        position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
        data: { name: n.id, label: n.label, purpose: n.purpose },
      }
    })

    // 병렬/양방향 엣지 감지: A→B 와 B→A 를 같은 쌍으로 취급 (정규화 키)
    // e.g. A→B, B→A 둘 다 pairKey = "A__B" (알파벳 정렬)
    const pairCounts: Record<string, number> = {}
    graphData.edges.forEach(e => {
      const pairKey = [e.source, e.target].sort().join('__')
      pairCounts[pairKey] = (pairCounts[pairKey] || 0) + 1
    })

    const pairSeen: Record<string, number> = {}
    const OFFSET_STEP = 60  // 병렬/양방향 엣지 간 간격 (px)

    // GraphEdge → React Flow Edge (겹침 방지 오프셋 포함)
    const rfEdges: Edge<CustomEdgeData>[] = graphData.edges.map((e, i) => {
      const pairKey = [e.source, e.target].sort().join('__')
      const total = pairCounts[pairKey]
      const idx = pairSeen[pairKey] = (pairSeen[pairKey] ?? -1) + 1
      // total=1 → 0, total=2 → -30/+30, total=3 → -60/0/+60
      const offset = total > 1 ? (idx - (total - 1) / 2) * OFFSET_STEP : 0

      return {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        type: 'customEdge',
        data: { relation: e.relation, offset },
      }
    })

    return { rfNodes, rfEdges }
  }, [graphData])
}
