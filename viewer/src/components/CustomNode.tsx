// Design Ref: §5.4 — CustomNode: 클래스명 + 한글 레이블, 선택 시 파란 테두리
// @xyflow/react v12: NodeProps<Node<Data>> 패턴 사용
import { type Node, type NodeProps, Handle, Position } from '@xyflow/react'
import { CustomNodeData } from '../types/graph'
import './CustomNode.css'

type CustomNodeType = Node<CustomNodeData, 'customNode'>

export function CustomNode({ data, selected }: NodeProps<CustomNodeType>) {
  return (
    <div className={`custom-node${selected ? ' custom-node--selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="custom-node-name">{data.name}</div>
      <div className="custom-node-label">{data.label}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
