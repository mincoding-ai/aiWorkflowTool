# Plan — Semantic Graph Viewer (Plan Plus)

**작성일**: 2026-04-07  
**작성 방법**: /plan-plus (Brainstorming-Enhanced)  
**상태**: Approved

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | graph.json 텍스트 파일만으로는 코드 구조의 의미 관계를 직관적으로 파악하기 어렵다 |
| **Solution** | React Flow 기반 인터랙티브 그래프로 Node·Edge를 시각화, 클릭 시 상세 정보 표시 |
| **Function UX Effect** | graph.json을 드래그앤드롭하면 즉시 코드 구조 그래프가 화면에 펼쳐진다 |
| **Core Value** | Analyzer가 생성한 의미 구조를 한눈에 탐색하여 레거시 코드 이해 속도 극대화 |

---

## 1. User Intent Discovery

- **핵심 문제**: graph.json의 nodes/edges를 텍스트로 읽는 것은 직관성이 없음
- **주요 사용자**: Analyzer로 분석을 마친 개발자 (코드 구조 탐색 목적)
- **성공 기준**: graph.json 로드 후 30초 이내에 주요 클래스 간 관계를 파악할 수 있음

---

## 2. 아키텍처 결정

| 결정 | 선택 | 이유 |
|------|------|------|
| 그래프 라이브러리 | @xyflow/react (React Flow v12) | React 네이티브, TS 완전 지원, 커스텀 노드/엣지 JSX |
| 빌드 도구 | Vite + React + TypeScript | PRD 확정 스택 |
| 상태관리 | React useState / useCallback | 규모 작음, 외부 라이브러리 불필요 |
| 파일 로드 | 파일 피커 + 드래그앤드롭 | 백엔드 없이 로컬 파일 직접 처리 |
| 레이아웃 알고리즘 | dagre (계층형) | 의존성 그래프에 가장 직관적 |

---

## 3. V1 범위 (Confirmed)

### 포함
- graph.json 로드 (파일 선택 버튼 + 드래그앤드롭)
- 인터랙티브 그래프 렌더링 (React Flow + dagre 자동 레이아웃)
- 커스텀 노드 (이름 + 레이블 표시, 선택 시 하이라이트)
- 커스텀 엣지 (관계 레이블 표시)
- 노드 클릭 → 우측 상세 패널 (목적 전문 표시 + 연결 엣지 목록)
- 줌/패닝/미니맵/줌 컨트롤

### V2로 연기
- 노드 검색/필터
- 다크모드
- 그래프 PNG 내보내기
- Analyzer 산출물 디렉토리 직접 감시 (파일 변경 자동 반영)

---

## 4. 폴더 구조

```
viewer/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.tsx               # React 진입점
    ├── App.tsx                # 루트 컴포넌트 (레이아웃)
    ├── types/
    │   └── graph.ts           # GraphData, GraphNode, GraphEdge 타입
    ├── hooks/
    │   ├── useGraphLoader.ts  # graph.json 파일 로드 훅
    │   └── useLayout.ts       # dagre 자동 레이아웃 훅
    └── components/
        ├── GraphCanvas.tsx    # React Flow 캔버스 래퍼
        ├── CustomNode.tsx     # 커스텀 노드 컴포넌트
        ├── CustomEdge.tsx     # 엣지 레이블 컴포넌트
        ├── DetailPanel.tsx    # 노드 클릭 상세 패널
        └── FileDropZone.tsx   # 파일 로드 영역 (초기 화면)
```

---

## 5. graph.json 입력 스키마

```typescript
interface GraphData {
  generated_at: string;
  nodes: Array<{
    id: string;
    label: string;
    purpose: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    relation: string;
  }>;
}
```

---

## 6. UI 레이아웃

```
┌─────────────────────────────────────────────────┐
│  Semantic Graph Viewer         [graph.json 열기] │
├──────────────────────────────┬──────────────────┤
│                              │  📌 선택된 노드   │
│   [React Flow 캔버스]        │  ────────────     │
│   • 노드: 클래스명 + 레이블   │  UserManager     │
│   • 엣지: 관계 레이블         │  사용자 관리 레이어│
│   • 줌/패닝 가능              │                  │
│   • 클릭으로 노드 선택        │  목적:            │
│                              │  사용자 생성·삭제  │
│   [미니맵]  [+][-][⊞]       │  를 처리하는...   │
│                              │                  │
│                              │  연결 관계:       │
│                              │  → Logger (사용)  │
└──────────────────────────────┴──────────────────┘
```

---

## 7. 데이터 흐름

```
[graph.json 파일]
    ↓ 드래그앤드롭 / 파일 선택
[useGraphLoader] → GraphData 파싱 + 유효성 검증
    ↓
[useLayout (dagre)] → React Flow nodes/edges 위치 계산
    ↓
[GraphCanvas] → React Flow 렌더링
    ↓ 노드 클릭
[DetailPanel] → 선택 노드 purpose + 연결 엣지 표시
```

---

## 8. 구현 세션 계획

> 각 세션: **plan.md 기록 → 구현 → 코드 테스트 → 인간 테스트**

### Session 1: 프로젝트 셋업 + 기본 그래프 렌더링
**대상 파일**: `package.json`, `vite.config.ts`, `tsconfig.json`, `src/types/graph.ts`, `src/App.tsx`, `src/components/GraphCanvas.tsx`

**구현 범위**:
- `npm create vite@latest viewer -- --template react-ts`
- 의존성: `@xyflow/react`, `dagre`, `@types/dagre`
- `GraphData` 타입 정의
- 하드코딩된 샘플 graph.json으로 React Flow 기본 렌더링 확인

**코드 테스트**: 타입 컴파일 + 브라우저에서 노드/엣지 표시 확인

---

### Session 2: graph.json 로더 (FileDropZone + useGraphLoader)
**대상 파일**: `src/hooks/useGraphLoader.ts`, `src/components/FileDropZone.tsx`

**구현 범위**:
- `FileReader` API로 로컬 파일 읽기
- 파일 선택 버튼 + 드래그앤드롭 이벤트
- JSON 파싱 + GraphData 유효성 검증 (nodes/edges 키 존재 여부)
- 오류 시 에러 메시지 표시

**코드 테스트**: 실제 graph.json 로드 → 파싱 성공 확인

---

### Session 3: dagre 자동 레이아웃 + 커스텀 노드/엣지
**대상 파일**: `src/hooks/useLayout.ts`, `src/components/CustomNode.tsx`, `src/components/CustomEdge.tsx`

**구현 범위**:
- `dagre.graphlib.Graph`로 계층형 레이아웃 계산
- `CustomNode`: 클래스명 + 레이블 표시, 선택 시 테두리 강조
- `CustomEdge`: 엣지 중앙에 `relation` 레이블 표시 (EdgeLabelRenderer)
- 전체 그래프 fit-to-view

**코드 테스트**: 실제 graph.json 로드 후 레이아웃 정렬 육안 확인

---

### Session 4: 상세 패널 (DetailPanel)
**대상 파일**: `src/components/DetailPanel.tsx`, `src/App.tsx` (상태 연결)

**구현 범위**:
- 노드 클릭 → 선택 상태 관리 (`selectedNode`)
- `DetailPanel`: 노드 이름, 레이블, 목적 전문 표시
- 연결된 엣지 목록 (source/target 방향 + relation 표시)
- 노드 미선택 시 "노드를 클릭하세요" 안내

**코드 테스트**: 노드 클릭 → 패널 내용 정확성 확인

---

### Session 5: UX 마감 + 통합 확인
**대상 파일**: `src/App.tsx`, CSS, `README.md`

**구현 범위**:
- 미니맵, 줌 컨트롤, 배경 격자
- 빈 graph (노드 0개) 예외 처리
- `viewer/README.md` 사용 방법 작성

**최종 인간 테스트**: Analyzer 실제 산출물 graph.json 로드 → 전체 흐름 확인

---

## 9. 다음 단계

```
/pdca design semantic-viewer   → 상세 설계 (컴포넌트 인터페이스)
/pdca do semantic-viewer       → Session 1부터 구현
```
