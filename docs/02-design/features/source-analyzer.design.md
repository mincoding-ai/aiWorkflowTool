# Design — Source Code Analyzer

**작성일**: 2026-04-07  
**아키텍처**: Option C — Phase 기반 파이프라인 + 경량 상태파일  
**상태**: Draft

---

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | 주석/문서 없는 레거시 코드 온보딩 시간 단축 |
| **WHO** | 코드 인수인계를 받은 개발자 |
| **RISK** | GPT-4 토큰 한도 초과 (대용량 파일), 주석 삽입 후 코드 문법 오염 |
| **SUCCESS** | AI 생성 주석·문서만으로 코드 구조 파악 가능 |
| **SCOPE** | Python + wxPython Analyzer V1 (React Viewer는 V2) |

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────┐
│                  wxPython UI Layer               │
│  MainWindow  ←→  ProgressPanel  ←→  EventBus   │
└───────────────────────┬─────────────────────────┘
                        │ 이벤트 (콜백)
┌───────────────────────▼─────────────────────────┐
│              PipelineOrchestrator                │
│   Phase1 → Phase2 → Phase3 → Phase4 → Phase5   │
│              progress.json (상태 관리)           │
└──────┬──────────┬──────────┬──────────┬─────────┘
       │          │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────┐
  │FileScn │ │ClassExt│ │DepAnlz │ │ComntInj │
  │core/   │ │core/   │ │core/   │ │core/    │
  └────┬───┘ └───┬────┘ └───┬────┘ └──┬──────┘
       │          │          │          │
       └──────────┴──────────┴──────────┘
                        │
               ┌────────▼────────┐
               │  AI Client       │
               │  ai/client.py    │
               │  ai/prompts.py   │
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ GraphGenerator  │
               │ graph/          │
               └─────────────────┘
```

---

## 2. 모듈 구조

```
analyzer/
├── main.py                        # 앱 진입점
├── requirements.txt
├── src/
│   ├── ui/
│   │   ├── main_window.py         # wxPython 메인 창
│   │   └── progress_panel.py      # 진행 상황 패널 (실시간 업데이트)
│   ├── ai/
│   │   ├── client.py              # OpenAI API 래퍼
│   │   └── prompts.py             # Phase별 프롬프트 템플릿
│   ├── core/
│   │   ├── pipeline.py            # PipelineOrchestrator (Phase 제어)
│   │   ├── file_scanner.py        # 소스 파일 탐색 + 읽기
│   │   ├── class_extractor.py     # Python AST 기반 클래스 추출
│   │   ├── dependency_analyzer.py # 클래스 의존성 분석 + 위상 정렬
│   │   └── comment_injector.py    # 소스코드 주석 삽입
│   └── graph/
│       └── graph_generator.py     # graph.json 생성
└── tests/
    ├── test_file_scanner.py
    ├── test_class_extractor.py
    ├── test_dependency_analyzer.py
    └── test_comment_injector.py
```

---

## 3. 출력 디렉토리 구조

모든 산출물은 입력 소스코드 경로 내 `_ai_analysis/` 폴더에 저장됩니다.

```
{source_path}/
└── _ai_analysis/
    ├── progress.json      # 파이프라인 진행 상태 (이어하기용)
    ├── PRD.md             # Phase 1 산출물
    ├── DESIGN.md          # Phase 1 산출물
    ├── CLASS.md           # Phase 2 산출물
    ├── CLASS_ORDER.md     # Phase 3 산출물
    ├── analysis.md        # Phase 4 산출물 (클래스별 목적 요약)
    └── graph.json         # Phase 5 산출물
```

> 소스코드 파일 자체(주석 삽입)는 원본 위치에서 직접 수정됩니다.

---

## 4. progress.json 스키마

```json
{
  "source_path": "/path/to/source",
  "started_at": "2026-04-07T10:00:00",
  "phases": {
    "phase1": { "status": "completed", "completed_at": "..." },
    "phase2": { "status": "completed", "completed_at": "..." },
    "phase3": { "status": "pending" },
    "phase4": {
      "status": "in_progress",
      "total_classes": 20,
      "completed_classes": ["ClassA", "ClassB"]
    },
    "phase5": { "status": "pending" }
  }
}
```

**status 값**: `"pending"` | `"in_progress"` | `"completed"` | `"failed"`

---

## 5. Phase별 상세 설계

### Phase 1: 전체 개요 분석 (PRD.md + DESIGN.md 생성)

**담당 모듈**: `core/file_scanner.py` + `ai/client.py`  
**입력**: 소스코드 경로  
**출력**: `_ai_analysis/PRD.md`, `_ai_analysis/DESIGN.md`

#### 동작 흐름

```
1. FileScanner.scan(path)
   → 모든 .py 파일 경로 수집
   → 각 파일 내용 읽기
   → 파일 목록 + 내용 집계 (토큰 초과 시 요약본 사용)

2. AIClient.generate_overview(file_contents)
   → 프롬프트: PROMPT_OVERVIEW (prompts.py)
   → 응답: PRD 텍스트 + DESIGN 텍스트

3. 파일 저장
   → _ai_analysis/PRD.md
   → _ai_analysis/DESIGN.md
```

#### 토큰 관리 전략

| 파일 크기 | 처리 방식 |
|-----------|-----------|
| 전체 < 80K 토큰 | 전체 내용 전송 |
| 전체 >= 80K 토큰 | 각 파일 첫 50줄 + 함수 시그니처만 추출하여 요약 전송 |

#### 프롬프트 구조 (PROMPT_OVERVIEW)

```
당신은 소스코드 분석 전문가입니다.
다음 Python 소스코드를 분석하여 두 문서를 작성하세요.

[소스코드]
{file_contents}

## 출력 형식
### PRD.md
(이 프로젝트가 해결하는 문제, 주요 기능, 사용자 시나리오)

### DESIGN.md
(전체 아키텍처, 주요 컴포넌트, 데이터 흐름)
```

---

### Phase 2: 클래스 추출 (CLASS.md 생성)

**담당 모듈**: `core/class_extractor.py`  
**입력**: 소스코드 경로  
**출력**: `_ai_analysis/CLASS.md`

#### 동작 흐름

```
1. ClassExtractor.extract(path)
   → pathlib로 모든 .py 파일 순회
   → ast.parse(source) 로 AST 파싱
   → ast.ClassDef 노드 수집
   → 각 클래스: 이름, 소속 파일, 줄 번호, 메서드 목록 추출

2. CLASS.md 생성
   → 클래스별 한 섹션
   → 형식: "## ClassName (file.py:10)"
   →       "메서드: method1(), method2(), ..."
```

#### CLASS.md 형식

```markdown
# CLASS.md

## UserManager (auth/user.py:15)
- 메서드: create_user(), delete_user(), get_user()
- 기반 클래스: BaseManager

## DatabaseConnection (db/connection.py:5)
- 메서드: connect(), disconnect(), execute()
- 기반 클래스: -
```

#### ClassInfo 데이터 클래스

```python
@dataclass
class ClassInfo:
    name: str
    file_path: str
    line_number: int
    methods: List[str]
    base_classes: List[str]
    source_code: str        # 클래스 전체 소스 (Phase 4에서 사용)
```

---

### Phase 3: 의존성 분석 + 정렬 (CLASS_ORDER.md 생성)

**담당 모듈**: `core/dependency_analyzer.py`  
**입력**: ClassInfo 목록 (Phase 2 결과)  
**출력**: `_ai_analysis/CLASS_ORDER.md`

#### 의존성 정의

> A 클래스 내부에서 B 클래스의 인스턴스를 생성하거나 B의 메서드를 직접 호출하면,  
> A는 B에 의존한다.

#### 동작 흐름

```
1. 각 ClassInfo.source_code에서 타 클래스 참조 탐색
   → ast.Name, ast.Attribute 노드에서 알려진 클래스명 매칭
   → 의존성 그래프 딕셔너리 생성: { "ClassA": ["ClassB", "ClassC"] }

2. 위상 정렬 (Topological Sort)
   → collections.deque + 진입 차수(in-degree) 방식
   → 순환 의존성 발견 시: 경고 기록 후 임의 순서로 처리

3. CLASS_ORDER.md 생성
   → 정렬된 순서로 클래스명 나열
   → 각 클래스의 의존 대상 명시

4. 검증: CLASS.md 클래스 수 == CLASS_ORDER.md 클래스 수
   → 불일치 시 누락 클래스 목록 경고 출력
```

#### CLASS_ORDER.md 형식

```markdown
# CLASS_ORDER.md
# 분석 순서: 단순(의존성 없음) → 복잡(다수 의존)

1. DatabaseConnection  (의존: 없음)
2. BaseManager         (의존: DatabaseConnection)
3. UserManager         (의존: BaseManager, DatabaseConnection)
4. AuthService         (의존: UserManager, DatabaseConnection)
```

---

### Phase 4: 클래스별 주석 삽입 (analysis.md 생성)

**담당 모듈**: `core/comment_injector.py` + `ai/client.py`  
**입력**: CLASS_ORDER.md 순서, 각 ClassInfo, PRD.md, DESIGN.md  
**출력**: 각 소스파일에 주석 삽입 (in-place), `_ai_analysis/analysis.md`

#### 동작 흐름 (클래스 단위 반복)

```
for class_info in ordered_classes:
    if class_info.name in progress["completed_classes"]:
        continue  # 이미 완료된 클래스 스킵 (이어하기)

    1. AIClient.analyze_class(class_info, prd_content, design_content)
       → 프롬프트: PROMPT_COMMENT (prompts.py)
       → 응답: 주석이 달린 클래스 소스코드 전문

    2. CommentInjector.inject(file_path, class_name, commented_source)
       → 원본 파일에서 클래스 범위 (line_start ~ line_end) 찾기
       → 해당 범위를 응답 내용으로 교체
       → 파일 저장

    3. analysis.md에 한 줄 추가
       → "{class_name} : {AI가 생성한 클래스 목적 한 줄}"

    4. progress.json 업데이트
       → completed_classes에 추가
       → UI에 진행률 이벤트 발행
```

#### 주석 삽입 규칙

| 위치 | 내용 |
|------|------|
| 클래스 정의 바로 아래 | 클래스 목적 docstring (한글 1~3줄) |
| 각 메서드 정의 바로 아래 | 메서드 목적 + 파라미터 + 반환값 docstring |
| 메서드 내부 주요 로직 | 인라인 주석 (`# 설명`) |

#### 프롬프트 구조 (PROMPT_COMMENT)

```
다음은 프로젝트 개요입니다:
[PRD]
{prd_content}

[DESIGN]  
{design_content}

위 맥락을 참고하여, 아래 Python 클래스에 한글 주석을 추가하세요.
규칙:
- 클래스 docstring: 이 클래스의 역할을 1~3줄로 설명
- 메서드 docstring: 목적, Args, Returns 형식
- 내부 주석: 핵심 로직만 (자명한 코드는 생략)
- 원본 로직은 절대 수정하지 말 것

[원본 클래스 소스]
{class_source}

[주석이 달린 클래스 소스코드만 출력하세요]
```

#### analysis.md 형식

```markdown
# analysis.md

DatabaseConnection : 데이터베이스 연결 생성 및 쿼리 실행을 담당하는 기반 클래스
BaseManager : CRUD 공통 로직을 추상화한 기반 매니저
UserManager : 사용자 생성·삭제·조회를 처리하는 비즈니스 로직 레이어
AuthService : 로그인·토큰 발급·권한 검증을 담당하는 인증 서비스
```

---

### Phase 5: 그래프 데이터 생성 (graph.json)

**담당 모듈**: `graph/graph_generator.py` + `ai/client.py`  
**입력**: `analysis.md`, `CLASS_ORDER.md` (의존성 그래프)  
**출력**: `_ai_analysis/graph.json`

#### 동작 흐름

```
1. analysis.md 파싱 → {클래스명: 목적} 딕셔너리

2. AIClient.extract_semantic_nodes(analysis_content, design_content)
   → 프롬프트: PROMPT_GRAPH_NODES
   → 응답: 의미론적으로 핵심인 Node 목록 (전체 클래스의 일부일 수 있음)

3. AIClient.extract_semantic_edges(nodes, dependency_graph)
   → 프롬프트: PROMPT_GRAPH_EDGES
   → 응답: Node 간 의미적 관계 (한글 레이블)

4. graph.json 저장
```

#### graph.json 스키마

```json
{
  "generated_at": "2026-04-07T10:30:00",
  "source_path": "/path/to/source",
  "nodes": [
    {
      "id": "UserManager",
      "label": "사용자 관리",
      "purpose": "사용자 생성·삭제·조회를 처리하는 비즈니스 로직 레이어"
    }
  ],
  "edges": [
    {
      "source": "AuthService",
      "target": "UserManager",
      "relation": "사용자 정보를 조회하여 인증 처리"
    }
  ]
}
```

#### 프롬프트 구조 (PROMPT_GRAPH_NODES)

```
다음은 소스코드 분석 결과입니다:
{analysis_content}

이 중에서 의미론적으로 핵심이 되는 컴포넌트(Node)를 추출하세요.
- 너무 세부적인 유틸리티 클래스는 제외
- 시스템의 주요 책임을 담당하는 클래스 위주로 선택
- 각 Node에 한 줄로 목적을 한글로 설명

JSON 형식으로만 출력:
[{"id": "...", "label": "...", "purpose": "..."}]
```

---

## 6. UI 설계 (wxPython)

### MainWindow 레이아웃

```
┌─────────────────────────────────────────┐
│  Source Code Analyzer                   │
├─────────────────────────────────────────┤
│  소스코드 경로:                          │
│  [____________________________] [찾기]  │
│                                         │
│  [   분석 시작   ]  [   이어서 시작   ] │
├─────────────────────────────────────────┤
│  진행 상황:                             │
│  ████████████░░░░░░░  Phase 3/5 (60%)  │
│  현재: CLASS_ORDER.md 생성 중...       │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ [로그 출력 영역]               │   │
│  │ ✅ Phase 1 완료: PRD.md 생성   │   │
│  │ ✅ Phase 2 완료: 23개 클래스   │   │
│  │ 🔄 Phase 3: 의존성 분석 중...  │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### UI 이벤트 모델

```python
# 파이프라인 → UI 이벤트 (wx.CallAfter 사용)
EVT_PHASE_START   = "phase_start"   # {"phase": 1, "name": "개요 분석"}
EVT_PHASE_DONE    = "phase_done"    # {"phase": 1}
EVT_CLASS_DONE    = "class_done"    # {"class": "UserManager", "index": 3, "total": 23}
EVT_PIPELINE_DONE = "pipeline_done" # {}
EVT_ERROR         = "error"         # {"message": "...", "phase": 1}
```

---

## 7. AI Client 설계

### client.py 인터페이스

```python
class AIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        ...

    def generate_overview(self, file_contents: str) -> tuple[str, str]:
        """PRD 텍스트, DESIGN 텍스트 반환"""

    def analyze_class(
        self,
        class_info: ClassInfo,
        prd: str,
        design: str
    ) -> tuple[str, str]:
        """주석 달린 소스코드, 클래스 목적 한 줄 반환"""

    def extract_semantic_nodes(self, analysis: str, design: str) -> list[dict]:
        """Node 목록 반환"""

    def extract_semantic_edges(self, nodes: list, dep_graph: dict) -> list[dict]:
        """Edge 목록 반환"""

    def _call(self, prompt: str, max_tokens: int = 4096) -> str:
        """OpenAI API 호출 (재시도 3회)"""
```

---

## 8. PipelineOrchestrator 설계

```python
class PipelineOrchestrator:
    def __init__(self, source_path: str, api_key: str, callback: Callable):
        self.source_path = Path(source_path)
        self.output_dir = self.source_path / "_ai_analysis"
        self.progress = self._load_progress()
        self.callback = callback  # UI 이벤트 콜백

    def run(self, resume: bool = False):
        """전체 파이프라인 실행"""
        phases = [
            ("phase1", self._run_phase1),
            ("phase2", self._run_phase2),
            ("phase3", self._run_phase3),
            ("phase4", self._run_phase4),
            ("phase5", self._run_phase5),
        ]
        for phase_id, phase_fn in phases:
            if resume and self.progress["phases"][phase_id]["status"] == "completed":
                continue
            phase_fn()
            self._mark_phase_done(phase_id)
```

---

## 9. requirements.txt

```
wxPython>=4.2.0
openai>=1.0.0
```

---

## 10. 에러 처리

| 상황 | 처리 |
|------|------|
| OpenAI API 오류 (429/500) | 지수 백오프 재시도 3회 |
| 파일 파싱 오류 (SyntaxError) | 해당 파일 스킵 + 로그 기록 |
| 주석 삽입 후 구문 오류 | 백업본 복구 (원본 .bak 파일 보존) |
| 순환 의존성 | 경고 기록 후 임의 순서 처리 |
| 중단 후 재시작 | progress.json 기반 완료 Phase 스킵 |

---

## 11. Implementation Guide

### 11.1 구현 순서 (Phase별)

| 세션 | 모듈 | 내용 |
|------|------|------|
| Session 1 | `ai/client.py`, `ai/prompts.py` | OpenAI 클라이언트 + 프롬프트 기반 |
| Session 2 | `core/file_scanner.py`, `core/class_extractor.py` | 파일 탐색 + AST 클래스 추출 |
| Session 3 | `core/dependency_analyzer.py` | 의존성 분석 + 위상 정렬 |
| Session 4 | `core/comment_injector.py` | 주석 삽입 (백업 포함) |
| Session 5 | `core/pipeline.py` | PipelineOrchestrator (progress.json 포함) |
| Session 6 | `graph/graph_generator.py` | graph.json 생성 |
| Session 7 | `ui/main_window.py`, `ui/progress_panel.py` | wxPython UI |
| Session 8 | `main.py`, `requirements.txt` | 진입점 + 통합 테스트 |

### 11.2 각 세션 시작 전 확인사항

- 이전 세션 모듈의 단위 테스트 통과 여부 확인
- `progress.json` 상태 확인 (이어하기 시)
- OpenAI API 키 환경변수 설정 여부 확인

### 11.3 Session Guide

```
/pdca do source-analyzer --scope session-1   # AI Client
/pdca do source-analyzer --scope session-2   # File Scanner + Class Extractor
/pdca do source-analyzer --scope session-3   # Dependency Analyzer
/pdca do source-analyzer --scope session-4   # Comment Injector
/pdca do source-analyzer --scope session-5   # Pipeline Orchestrator
/pdca do source-analyzer --scope session-6   # Graph Generator
/pdca do source-analyzer --scope session-7   # wxPython UI
/pdca do source-analyzer --scope session-8   # Integration & main.py
```
