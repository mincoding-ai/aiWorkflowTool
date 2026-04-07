// Design Ref: §5.1 — 상태는 App.tsx에만 존재. 컴포넌트는 Props만 받는 순수 표현 계층
import { useState, useMemo } from 'react'
import { GraphCanvas } from './components/GraphCanvas'
import { FileDropZone } from './components/FileDropZone'
import { DetailPanel } from './components/DetailPanel'
import { useGraphLoader } from './hooks/useGraphLoader'
import { useLayout } from './hooks/useLayout'

export default function App() {
  const { graphData, error, loadFile, reset } = useGraphLoader()
  const { rfNodes, rfEdges } = useLayout(graphData)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Plan SC: graph.json 로드 후 30초 이내 클래스 관계 파악
  const selectedNode = useMemo(
    () => graphData?.nodes.find(n => n.id === selectedNodeId) ?? null,
    [graphData, selectedNodeId]
  )

  const handleReset = () => {
    reset()
    setSelectedNodeId(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Semantic Graph Viewer</h1>
        {graphData && (
          <>
            <span className="app-header-meta">
              노드 {graphData.nodes.length}개 · 엣지 {graphData.edges.length}개
            </span>
            <button className="app-header-reset" onClick={handleReset} type="button">
              다른 파일 열기
            </button>
          </>
        )}
      </header>

      <main className="app-body">
        {!graphData ? (
          <FileDropZone onLoad={loadFile} error={error} />
        ) : (
          <>
            <div className="graph-area">
              {rfNodes.length === 0 ? (
                <div className="graph-empty">노드가 없습니다</div>
              ) : (
                <GraphCanvas
                  nodes={rfNodes}
                  edges={rfEdges}
                  selectedNodeId={selectedNodeId}
                  onNodeClick={setSelectedNodeId}
                />
              )}
            </div>

            <aside className="detail-panel">
              <DetailPanel
                selectedNode={selectedNode}
                allEdges={graphData.edges}
              />
            </aside>
          </>
        )}
      </main>
    </div>
  )
}
