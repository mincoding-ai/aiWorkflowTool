// Design Ref: §4.1 — useGraphLoader: FileReader 기반 로컬 파일 로드 훅
import { useState, useCallback } from 'react'
import { GraphData, GraphNode, GraphEdge } from '../types/graph'

interface UseGraphLoaderReturn {
  graphData: GraphData | null;
  error: string | null;
  loadFile: (file: File) => void;
  reset: () => void;
}

// Design Ref: §9 — 런타임 필드 검증 타입 가드 (타입 단언 대체)
function isValidNode(n: unknown): n is GraphNode {
  return typeof n === 'object' && n !== null
    && typeof (n as GraphNode).id === 'string'
    && typeof (n as GraphNode).label === 'string'
    && typeof (n as GraphNode).purpose === 'string'
}

function isValidEdge(e: unknown): e is GraphEdge {
  return typeof e === 'object' && e !== null
    && typeof (e as GraphEdge).source === 'string'
    && typeof (e as GraphEdge).target === 'string'
    && typeof (e as GraphEdge).relation === 'string'
}

export function useGraphLoader(): UseGraphLoaderReturn {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadFile = useCallback((file: File) => {
    // Design Ref: §9 — 예외 처리: .json 아닌 파일
    if (!file.name.endsWith('.json')) {
      setError('JSON 파일만 지원합니다')
      return
    }

    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string)

        // Design Ref: §9 — 예외 처리: nodes/edges 키 없음
        if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
          setError('graph.json 형식이 올바르지 않습니다')
          return
        }

        // 필드 레벨 유효성 검증 (타입 단언 대체)
        if (!parsed.nodes.every(isValidNode)) {
          setError('노드에 id·label·purpose 필드가 필요합니다')
          return
        }
        if (!parsed.edges.every(isValidEdge)) {
          setError('엣지에 source·target·relation 필드가 필요합니다')
          return
        }

        setError(null)
        setGraphData({ generated_at: parsed.generated_at ?? '', nodes: parsed.nodes, edges: parsed.edges })
      } catch {
        // Design Ref: §9 — 예외 처리: 잘못된 JSON
        setError('유효한 JSON 파일이 아닙니다')
      }
    }

    reader.readAsText(file)
  }, [])

  const reset = useCallback(() => {
    setGraphData(null)
    setError(null)
  }, [])

  return { graphData, error, loadFile, reset }
}
