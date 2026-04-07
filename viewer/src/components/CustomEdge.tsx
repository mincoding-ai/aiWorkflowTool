// Design Ref: §5.5 — CustomEdge: BaseEdge + EdgeLabelRenderer로 relation 레이블 표시
// 병렬 엣지: offset 값으로 수직 이차 베지어 곡선 분리
// 드래그 핸들: 중간점을 드래그해 엣지 곡률 조절
// hover는 CSS로 처리 — useState 제거로 엣지별 불필요한 리렌더 방지
import { type Edge, type EdgeProps, getBezierPath, EdgeLabelRenderer, BaseEdge, useReactFlow } from '@xyflow/react'
import { CustomEdgeData } from '../types/graph'
import './CustomEdge.css'

type CustomEdgeType = Edge<CustomEdgeData, 'customEdge'>

export function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style,
}: EdgeProps<CustomEdgeType>) {
  const { setEdges, getViewport } = useReactFlow()

  const offset = data?.offset ?? 0

  // 엣지 방향의 수직 단위벡터 (드래그 계산에 사용)
  const dx = targetX - sourceX
  const dy = targetY - sourceY
  const len = Math.sqrt(dx * dx + dy * dy) || 1
  const nx = -dy / len
  const ny = dx / len

  let edgePath: string
  let labelX: number
  let labelY: number

  if (offset === 0) {
    // 오프셋 없을 땐 React Flow 기본 베지어 (포트 방향 고려)
    ;[edgePath, labelX, labelY] = getBezierPath({
      sourceX, sourceY, sourcePosition,
      targetX, targetY, targetPosition,
    })
  } else {
    // 수직 오프셋 적용 이차 베지어
    const cx = (sourceX + targetX) / 2 + nx * offset
    const cy = (sourceY + targetY) / 2 + ny * offset
    edgePath = `M ${sourceX} ${sourceY} Q ${cx} ${cy} ${targetX} ${targetY}`

    // 레이블은 제어점(cx,cy)이 아닌 실제 곡선 위 t=0.5 지점에 배치
    // B(0.5) = 0.25·P0 + 0.5·P1(control) + 0.25·P2
    labelX = 0.25 * sourceX + 0.5 * cx + 0.25 * targetX
    labelY = 0.25 * sourceY + 0.5 * cy + 0.25 * targetY
  }

  // 중간점 드래그: 마우스 이동을 수직 방향으로 분해해 offset 업데이트
  const handleDragStart = (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()

    const startClientX = e.clientX
    const startClientY = e.clientY
    const startOffset = offset

    const onMouseMove = (me: MouseEvent) => {
      const { zoom } = getViewport()
      // 마우스 이동량을 플로우 좌표로 변환 후 수직벡터에 투영
      const dFlowX = (me.clientX - startClientX) / zoom
      const dFlowY = (me.clientY - startClientY) / zoom
      const deltaPerp = dFlowX * nx + dFlowY * ny
      const newOffset = startOffset + deltaPerp

      setEdges(edges =>
        edges.map(edge =>
          edge.id === id
            ? { ...edge, data: { ...edge.data, offset: newOffset } }
            : edge
        )
      )
    }

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        {/* 레이블 + 드래그 핸들 컨테이너 — hover는 CSS로 처리 */}
        <div
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          className="edge-label-wrapper nodrag nopan"
        >
          {/* 관계 레이블 */}
          {data?.relation && (
            <div style={{
              background: 'rgba(255,255,255,0.9)',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '11px',
              color: '#374151',
              border: '1px solid #e5e7eb',
              whiteSpace: 'nowrap',
              userSelect: 'none',
            }}>
              {data.relation}
            </div>
          )}
          {/* 드래그 핸들 도트 — CSS .edge-label-wrapper:hover로 표시 */}
          <div
            onMouseDown={handleDragStart}
            className="edge-drag-handle"
            style={{ border: `2px solid ${(style as React.CSSProperties)?.stroke ?? '#94a3b8'}` }}
          />
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
