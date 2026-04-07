# Design — Semantic Graph Viewer

**작성일**: 2026-04-07  
**아키텍처**: React Flow + dagre 계층형 레이아웃 + 단방향 Props 흐름  
**상태**: Draft

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | graph.json 텍스트만으로는 코드 의미 관계 파악이 어렵다 |
| **WHO** | Analyzer 분석을 완료한 개발자 |
| **RISK** | dagre 레이아웃이 대규모 그래프(100+ 노드)에서 느릴 수 있음 |
| **SUCCESS** | graph.json 로드 후 30초 이내 클래스 관계 파악 가능 |
| **SCOPE** | React + Vite + TS V1 (검색/다크모드/내보내기는 V2) |

---

## 1. 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────┐
│                         App.tsx                              │
│   state: graphData | selectedNodeId                          │
├──────────────┬───────────────────────────────────────────────┤
│              │                                               │
│   useGraphLoader()          useLayout(graphData)             │
│   → loadFile / error        → rfNodes, rfEdges (dagre 배치)  │
│              │                                               │
├──────────────▼───────────────────────────────────────────────┤
│  !graphData → FileDropZone                                   │
│   graphData →                                                │
│    ┌──────────────────────────┬─────────────────────────┐   │
│    │     GraphCanvas          │      DetailPanel         │   │
│    │  <ReactFlow              │   selectedNode.purpose   │   │
│    │    nodeTypes={customNode}│   + 연결 엣지 목록        │   │
│    │    edgeTypes={customEdge}│                          │   │
│    │    onNodeClick →         │                          │   │
│    │    setSelectedNodeId />  │                          │   │
│    │  <MiniMap />             │                          │   │
│    │  <Controls />            │                          │   │
│    │  <Background />          │                          │   │
│    └──────────────────────────┴─────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**핵심 원칙**: 상태는 `App.tsx` 에만 존재. 컴포넌트는 Props만 받는 순수 표현 계층.

---

## 2. 모듈 구조

```
viewer/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── App.css
│   ├── types/
│   │   └── graph.ts
│   ├── hooks/
│   │   ├── useGraphLoader.ts
│   │   └── useLayout.ts
│   └── components/
│       ├── FileDropZone.tsx
│       ├── FileDropZone.css
│       ├── GraphCanvas.tsx
│       ├── CustomNode.tsx
│       ├── CustomNode.css
│       ├── CustomEdge.tsx
│       ├── CustomEdge.css
│       ├── DetailPanel.tsx
│       └── DetailPanel.css
└── public/
    └── sample-graph.json     # 개발용 샘플
```

---

## 3. 타입 정의 (`src/types/graph.ts`)

```typescript
// Analyzer graph.json 스키마와 1:1 대응
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
  offset?: number;  // 병렬 엣지 수직 분리 오프셋 (px). 드래그 조절 가능. 0 = 직선.
}
```

---

## 4. 훅 인터페이스

### 4.1 `useGraphLoader`

```typescript
interface UseGraphLoaderReturn {
  graphData: GraphData | null;   // 파싱된 그래프 데이터 (null = 미로드)
  error: string | null;          // 파싱/유효성 오류 메시지
  loadFile: (file: File) => void; // FileReader로 파일 읽기 트리거
  reset: () => void;             // graphData 초기화 (다른 파일 열기)
}

export function useGraphLoader(): UseGraphLoaderReturn
```

**내부 동작:**
1. `FileReader.readAsText(file)` → `onload` 콜백에서 `JSON.parse`
2. `nodes` / `edges` 배열 존재 여부 검증 → 실패 시 `error` 설정
3. 성공 시 `setGraphData(parsed)`

### 4.2 `useLayout`

```typescript
const NODE_WIDTH = 200;  // px
const NODE_HEIGHT = 70;  // px

interface UseLayoutReturn {
  rfNodes: Node<CustomNodeData>[];   // React Flow용 위치 계산된 노드
  rfEdges: Edge<CustomEdgeData>[];   // React Flow용 엣지
}

export function useLayout(graphData: GraphData | null): UseLayoutReturn
```

**내부 동작:**
1. `GraphNode[]` → `Node<CustomNodeData>[]` 변환 (id, type='customNode', data)
2. `GraphEdge[]` → `Edge<CustomEdgeData>[]` 변환 (id, source, target, type='customEdge', data)
3. `dagre.graphlib.Graph` 에 노드/엣지 추가 → `dagre.layout()` 실행
4. dagre 계산 결과 `{ x, y }` → 각 노드 `position` 에 반영
5. `graphData` 변경 시 재계산 (`useMemo` 또는 `useEffect`)

---

## 5. 컴포넌트 인터페이스

### 5.1 `App.tsx`

```typescript
// 상태
const [graphData, setGraphData] = useState<GraphData | null>(null);
const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

// 파생 값
const selectedNode = graphData?.nodes.find(n => n.id === selectedNodeId) ?? null;
// NOTE: coloredEdges 없음 — 색상 계산은 GraphCanvas 내부에서 처리
```

**렌더 분기:**
- `graphData === null` → `<FileDropZone>`
- `graphData !== null` → header + `<GraphCanvas nodes={rfNodes} edges={rfEdges} selectedNodeId={selectedNodeId}>` + `<DetailPanel>`

**설계 결정**: `coloredEdges` useMemo를 App에 두지 않는다.
선택 변경 시 App → GraphCanvas prop 전달만 발생하고, 색상 계산은 GraphCanvas 렌더 중 인라인 useMemo로 처리.
이로써 노드 클릭 시 **1회 렌더**만 발생 (useEffect→setEdges 제거).

### 5.2 `FileDropZone`

```typescript
interface FileDropZoneProps {
  onLoad: (file: File) => void;
  error: string | null;
}
```

**동작:**
- `<input type="file" accept=".json">` 숨김 처리, 버튼 클릭으로 트리거
- `onDragOver` / `onDrop` 이벤트로 드래그앤드롭 처리
- `error` 있으면 빨간 텍스트로 표시

**초기 화면:**
```
┌─────────────────────────────────────┐
│                                     │
│   graph.json을 드래그하거나          │
│   [파일 선택] 버튼을 클릭하세요      │
│                                     │
│   ── Analyzer 산출물 위치 ──         │
│   {source_path}/_ai_analysis/       │
│   graph.json                        │
└─────────────────────────────────────┘
```

### 5.3 `GraphCanvas`

```typescript
interface GraphCanvasProps {
  nodes: Node<CustomNodeData>[];
  edges: Edge<CustomEdgeData>[];       // 구조 전용 base 엣지 (색상 없음)
  selectedNodeId: string | null;       // 노드 선택 상태 — 색상 계산에 사용
  onNodeClick: (nodeId: string) => void;
}
```

**내부 동작:**
- `useEdgesState(propEdges)` — 로컬 엣지 상태 (드래그 offset 포함)
- `useEffect([propEdges])` — 파일 로드 시에만 엣지 구조 동기화 (O(n) Map 룩업, offset 보존)
- `displayEdges = useMemo([edges, selectedNodeId])` — 렌더 중 색상 인라인 계산, MarkerType.Arrow 추가

```tsx
// 색상 결정 로직 (GraphCanvas 내부)
const COLOR_OUTGOING = '#4F6EF7'  // → 파랑 (DetailPanel과 동일)
const COLOR_INCOMING = '#10b981'  // ← 초록 (DetailPanel과 동일)
const COLOR_DEFAULT  = '#94a3b8'  // 미선택 시 회색
const COLOR_DIMMED   = '#e2e8f0'  // 관련 없는 엣지

// ReactFlow에는 displayEdges 전달 (base edges 아님)
<ReactFlow
  nodes={nodes}
  edges={displayEdges}
  nodeTypes={{ customNode: CustomNode }}
  edgeTypes={{ customEdge: CustomEdge }}
  onNodeClick={(_, node) => onNodeClick(node.id)}
  fitView
>
  <MiniMap />
  <Controls />
  <Background variant="dots" gap={16} />
</ReactFlow>
```

**성능 특성:**
| 상황 | useEffect 발동 | 렌더 횟수 |
|------|----------------|-----------|
| 노드 클릭 (선택 변경) | ✗ (propEdges 불변) | 1회 |
| 새 파일 로드 | ✓ (엣지 구조 리셋) | 2회 (정상) |

### 5.4 `CustomNode`

```typescript
// React Flow NodeProps<CustomNodeData>
```

**렌더:**
```
┌────────────────────────────┐
│  UserManager               │  ← node.data.name (클래스명)
│  사용자 관리 레이어          │  ← node.data.label (한글)
└────────────────────────────┘
```

- 선택 시: `border: 2px solid #4F6EF7` (파란 테두리)
- 비선택: `border: 1px solid #ccc`
- Handle: source(아래) + target(위) — React Flow 기본

### 5.5 `CustomEdge`

```typescript
// React Flow EdgeProps<Edge<CustomEdgeData, 'customEdge'>>
```

**렌더:**
- `BaseEdge` — 엣지 선 렌더링 (MarkerType.Arrow 방향 화살표)
- `EdgeLabelRenderer` — 엣지 중앙에 relation 텍스트 + 드래그 핸들 오버레이

```
UserManager ─────[사용자 정보를 조회]────→ Logger
```

**병렬 엣지 처리 (`offset`):**
- `offset === 0`: `getBezierPath()` (React Flow 기본 베지어, 포트 방향 고려)
- `offset !== 0`: 수직 이차 베지어 `M sx sy Q cx cy tx ty`
  - 제어점: `(midX + nx*offset, midY + ny*offset)` (수직 단위벡터 활용)
  - 레이블 위치: `0.25·P0 + 0.5·P1 + 0.25·P2` (베지어 t=0.5 실제 위치)

**드래그 핸들:**
- `useReactFlow().setEdges()` + `document` 레벨 mousemove로 offset 실시간 업데이트
- 마우스 이동량을 수직벡터(nx, ny)에 투영 → `offset += dFlowX*nx + dFlowY*ny`
- hover 표시: `useState` 대신 CSS `.edge-label-wrapper:hover .edge-drag-handle { opacity: 1 }` (불필요한 리렌더 방지)

### 5.6 `DetailPanel`

```typescript
interface DetailPanelProps {
  selectedNode: GraphNode | null;  // null = 노드 미선택
  allEdges: GraphEdge[];           // 전체 엣지 (연결 필터용)
}
```

**렌더 (선택 시):**
```
📌 선택된 노드
─────────────────────
UserManager
사용자 관리 레이어

[목적]
사용자 생성·삭제·조회를 처리하는
비즈니스 로직 레이어

[연결 관계]
→ Logger  사용자 이벤트 로깅
← AuthService  사용자 정보 조회
```

- `→` (outgoing): `allEdges.filter(e => e.source === node.id)`
- `←` (incoming): `allEdges.filter(e => e.target === node.id)`

**렌더 (미선택 시):**
```
노드를 클릭하면
상세 정보가 표시됩니다.
```

---

## 6. 데이터 흐름 (상세)

```
File (drag/click)
    │
    ▼ useGraphLoader.loadFile()
FileReader.readAsText()
    │
    ▼ JSON.parse + validate
GraphData { nodes[], edges[] }
    │
    ▼ useLayout(graphData)
dagre.layout() + 병렬 엣지 offset 계산 (OFFSET_STEP=60px, sort() 정규화)
    │
    ▼
rfNodes: Node<CustomNodeData>[]  +  rfEdges: Edge<CustomEdgeData>[]  (구조만, 색상 없음)
    │                                        │
    ▼                                        ▼
App.tsx                              GraphCanvas
  selectedNodeId ──────────────────→   displayEdges = useMemo(edges + selectedNodeId)
  rfEdges ──────────────────────────→   색상 + MarkerType.Arrow 인라인 계산
                                        ↓
                                      ReactFlow (displayEdges)
                                        ↓
    ▼ onNodeClick(nodeId)            CustomEdge (offset 드래그 → setEdges)
App.selectedNodeId
    │
    ▼
DetailPanel (selectedNode + allEdges.filter — useMemo)
```

**노드 클릭 → 색상 반영 경로 (1회 렌더):**
```
click → setSelectedNodeId → [App render] → GraphCanvas(selectedNodeId prop 변경)
      → displayEdges useMemo 재계산 → ReactFlow 색상 즉시 반영
```

**파일 로드 → 엣지 구조 교체 경로 (2회 렌더, 정상):**
```
loadFile → setGraphData → [App render] → rfEdges 변경 → GraphCanvas(propEdges 변경)
         → useEffect 발동 → setEdges(리셋) → [GraphCanvas render]
```

---

## 7. 패키지 구성 (`package.json` 핵심)

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@xyflow/react": "^12.0.0",
    "dagre": "^0.8.5"
  },
  "devDependencies": {
    "@types/dagre": "^0.7.3",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

---

## 8. CSS / 스타일 전략

- **전역**: `App.css` — 레이아웃 (header/main/panel flex), React Flow 컨테이너 높이
- **컴포넌트별**: `*.css` (CSS Modules 미사용, 클래스명 접두사로 충돌 방지)
- **React Flow 필수**: `@xyflow/react/dist/style.css` import 필요

```css
/* App.css 핵심 */
.app { display: flex; flex-direction: column; height: 100vh; }
.app-header { height: 52px; display: flex; align-items: center; padding: 0 16px; }
.app-body { flex: 1; display: flex; overflow: hidden; }
.graph-area { flex: 1; }
.detail-panel { width: 280px; overflow-y: auto; border-left: 1px solid #e5e7eb; }
```

---

## 9. 예외 처리

| 상황 | 처리 |
|------|------|
| 잘못된 JSON | `error: "유효한 JSON 파일이 아닙니다"` |
| nodes/edges 키 없음 | `error: "graph.json 형식이 올바르지 않습니다"` |
| nodes 배열 비어있음 | 빈 그래프 렌더링 + "노드가 없습니다" 안내 |
| `.json` 아닌 파일 | `error: "JSON 파일만 지원합니다"` |

---

## 10. 개발 서버 설정

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
```

---

## 11. Implementation Guide

### 11.1 구현 순서

| 세션 | 파일 | 내용 |
|------|------|------|
| Session 1 | `package.json`, `tsconfig.json`, `vite.config.ts`, `types/graph.ts`, `App.tsx`, `GraphCanvas.tsx` | 프로젝트 셋업 + 샘플 데이터 React Flow 렌더링 |
| Session 2 | `hooks/useGraphLoader.ts`, `components/FileDropZone.tsx` | 파일 로드 + 드래그앤드롭 |
| Session 3 | `hooks/useLayout.ts`, `components/CustomNode.tsx`, `components/CustomEdge.tsx` | dagre 레이아웃 + 커스텀 노드/엣지 |
| Session 4 | `components/DetailPanel.tsx`, `App.tsx` (상태 연결) | 노드 클릭 상세 패널 |
| Session 5 | `App.css`, 예외처리, `README.md` | UX 마감 + 통합 확인 |

### 11.2 주요 확인사항

- `@xyflow/react/dist/style.css` 반드시 `main.tsx`에서 import
- dagre 설치 시 `@types/dagre` 별도 설치 필요
- React Flow 컨테이너에 명시적 `height` 필수 (flex `flex: 1` + `height: 100%`)

### 11.3 Session Guide

```
/pdca do semantic-viewer --scope session-1   # 셋업 + 기본 렌더링
/pdca do semantic-viewer --scope session-2   # 파일 로더
/pdca do semantic-viewer --scope session-3   # dagre + 커스텀 컴포넌트
/pdca do semantic-viewer --scope session-4   # 상세 패널
/pdca do semantic-viewer --scope session-5   # UX 마감
```
