# PRD — Source Code Analyzer & Semantic Viewer

**버전**: 0.1.0  
**작성일**: 2026-04-07  
**상태**: Draft

---

## 1. 개요

### 문제 정의

기존 소스코드를 빠르게 이해해야 할 때, 문서가 없거나 주석이 불충분한 경우가 많습니다.  
개발자가 코드베이스 전체를 파악하는 데 수일이 걸리는 문제를 AI로 해결합니다.

### 솔루션

1. **AI Analyzer** — AI가 코드를 읽고 문서를 생성하며 주석을 삽입
2. **Semantic Viewer** — 코드 구조를 그래프로 시각화하여 직관적으로 이해

---

## 2. 사용자 및 사용 시나리오

**주요 사용자**: 기존 코드베이스를 인수인계 받은 개발자, 레거시 코드 분석이 필요한 팀

**핵심 시나리오**:
1. 소스코드 경로를 앱에 입력
2. "분석 시작" 클릭 → AI가 자동으로 문서 + 주석 생성
3. `graph.json` 로드 → 코드 구조를 그래프로 탐색

---

## 3. 기능 요구사항

### 3.1 Tool 1: Source Code Analyzer (Python + wxPython)

#### 3.1.1 UI / 입력

| 요구사항 | 설명 |
|----------|------|
| REQ-UI-001 | 소스코드 폴더 경로 입력 필드 (파일 브라우저 지원) |
| REQ-UI-002 | 분석 시작 버튼 |
| REQ-UI-003 | 진행 상황 표시 (현재 처리 중인 클래스명 + 진행률) |
| REQ-UI-004 | 분석 완료 알림 |

#### 3.1.2 기능 1 — 분석 파이프라인

| 요구사항 | 설명 |
|----------|------|
| REQ-F1-001 | 대상 디렉토리의 모든 소스파일 탐색 (.py / .java / .cpp / .c / .h / .hpp) |
| REQ-F1-002 | GPT-4에게 전체 코드 구조 파악 요청 → `PRD.md` 생성 |
| REQ-F1-003 | 아키텍처 분석 → `DESIGN.md` 생성 |
| REQ-F1-004 | 전체 클래스 추출 → `CLASS.md` 생성 |
| REQ-F1-005 | 클래스 의존성 분석 (A가 B의 내부 함수 호출 → A가 B에 의존) |
| REQ-F1-006 | 의존성 기반 정렬 (단순 → 복잡) → `CLASS_ORDER.md` 생성 |
| REQ-F1-007 | `CLASS.md`의 모든 클래스가 `CLASS_ORDER.md`에 포함되는지 검증 |
| REQ-F1-008 | `CLASS_ORDER.md` 순서대로 클래스별 코드 분석 |
| REQ-F1-009 | 함수 정의부 상단에 docstring 삽입 |
| REQ-F1-010 | 함수 내부 주요 로직에 인라인 주석 삽입 |
| REQ-F1-011 | `PRD.md` / `DESIGN.md` 참조하여 문맥에 맞는 주석 생성 |
| REQ-F1-012 | 분석 완료 클래스를 `analysis.md`에 `클래스이름 : 목적` 형식으로 기록 |

#### 3.1.3 기능 2 — 그래프 데이터 생성

| 요구사항 | 설명 |
|----------|------|
| REQ-F2-001 | 기능 1 산출물 기반으로 의미론적 핵심 Node 추출 |
| REQ-F2-002 | 각 Node에 목적(한 줄 설명) 부여 |
| REQ-F2-003 | Node 간 의미적 연결 Edge 추출 |
| REQ-F2-004 | Edge에 관계 레이블 부여 (한글) |
| REQ-F2-005 | 결과를 `graph.json`으로 저장 |

**graph.json 스키마**:
```json
{
  "nodes": [
    { "id": "string", "label": "string", "purpose": "string" }
  ],
  "edges": [
    { "source": "string", "target": "string", "relation": "string (한글)" }
  ]
}
```

### 3.2 Tool 2: Semantic Graph Viewer (React + Vite + TS) — V2

| 요구사항 | 설명 |
|----------|------|
| REQ-V2-001 | `graph.json` 파일 로드 |
| REQ-V2-002 | Node + Edge를 인터랙티브 그래프로 렌더링 |
| REQ-V2-003 | Node 클릭 시 목적 표시 |
| REQ-V2-004 | Edge 레이블 표시 |

---

## 4. 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| AI API | OpenAI GPT-4 (gpt-4o 권장) |
| 언어 지원 | Python / Java / C / C++ (.py, .java, .cpp, .c, .h, .hpp) |
| 처리 단위 | 클래스 단위로 분할하여 API 호출 (토큰 한도 고려) |
| 출력 위치 | 분석 산출물은 입력 소스코드 디렉토리 내 `_ai_analysis/` 하위에 저장 |

---

## 5. 범위 외 (V2 이후)

- React Graph Viewer UI
- JavaScript / TypeScript 등 추가 언어 지원
- 실시간 스트리밍 분석 표시
- 분석 결과 diff (재분석 시 변경사항)

---

## 6. 기술 스택

| 컴포넌트 | 기술 |
|----------|------|
| Analyzer UI | Python 3.10+, wxPython 4.x |
| AI 연동 | OpenAI Python SDK (`openai`) |
| 파일 파싱 | `ast` (Python), 정규식 (Java/C/C++), `pathlib` |
| Viewer | React 18, Vite, TypeScript (V2) |
| 그래프 렌더링 | react-flow 또는 cytoscape.js (V2) |
