# Plan — Source Code Analyzer (Plan Plus)

**작성일**: 2026-04-07  
**작성 방법**: /plan-plus (Brainstorming-Enhanced)  
**상태**: Approved

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Problem** | 주석/문서 없는 코드베이스를 이해하는 데 과도한 시간 소요 |
| **Solution** | AI가 자동으로 문서 생성 + 주석 삽입 + 의미 그래프 데이터 생성 |
| **Function UX Effect** | 개발자가 앱에 경로만 입력하면 전체 파이프라인이 자동 실행 |
| **Core Value** | 레거시 코드 온보딩 시간을 수일 → 수십 분으로 단축 |

---

## 1. User Intent Discovery

- **핵심 문제**: 주석/문서 없는 소스코드 이해 시간 단축
- **주요 사용자**: 코드 인수인계를 받은 개발자
- **성공 기준**: AI가 생성한 주석과 문서만으로 코드 구조를 파악할 수 있음

---

## 2. 아키텍처 결정

| 결정 | 선택 | 이유 |
|------|------|------|
| AI Provider | OpenAI GPT-4 (gpt-4o) | 사용자 선택 |
| Repo 구조 | 모노레포 (analyzer/ + viewer/) | 데이터 공유 편의 |
| UI 프레임워크 | wxPython | 사용자 지정 |

---

## 3. V1 범위 (Confirmed)

### 포함
- Python + wxPython Analyzer 앱
- 지원 언어: Python / Java / C / C++ (`.py`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`)
- 분석 파이프라인 (PRD.md → DESIGN.md → CLASS.md → CLASS_ORDER.md → 주석 → analysis.md)
- Graph JSON 데이터 생성 (`graph.json`)

### V2로 연기
- React + Vite + TS Graph Viewer

---

## 4. 폴더 구조

```
프로젝트/
├── analyzer/
│   ├── src/
│   │   ├── ui/          # wxPython GUI (메인 창, 진행 표시)
│   │   ├── ai/          # OpenAI API 클라이언트 + 프롬프트
│   │   ├── core/        # 파일 탐색, 클래스 파싱, 의존성 분석
│   │   └── graph/       # graph.json 생성
│   ├── tests/
│   ├── requirements.txt
│   └── main.py
├── viewer/              # V2 (React + Vite + TS)
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── types/
├── docs/
│   ├── 01-plan/features/
│   └── 02-design/
├── PRD.md
└── README.md
```

---

## 5. 분석 파이프라인 플로우

```
[입력: 소스코드 경로]
    ↓
[1] 전체 파일 탐색 → GPT-4로 PRD.md + DESIGN.md 생성
    ↓
[2] 클래스 추출 → CLASS.md
    ↓
[3] 의존성 분석 → CLASS_ORDER.md (단순 → 복잡 순서)
    ↓
[4] 검증: CLASS.md ∩ CLASS_ORDER.md = 전체
    ↓
[5] 순서대로 클래스별 GPT-4 분석 → 주석 삽입 + analysis.md 기록
    ↓
[6] 전체 분석 완료 → graph.json 생성 (Node + Edge)
```

---

## 6. graph.json 스키마

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

---

## 7. 다음 단계

```
/pdca design source-analyzer   → 상세 설계 (모듈별 인터페이스)
/pdca do source-analyzer       → 구현
```

---

## 8. 구현 세션 진행 계획

> 각 세션: **계획 기록 → 구현 → 코드 테스트 → 인간 테스트** 순서로 진행

### Session 1: AI Client 모듈 (`ai/`)

**상태**: 완료 ✅ (16/16 테스트 통과)  
**대상 파일**:
- `analyzer/src/ai/client.py` — OpenAI API 래퍼 클래스
- `analyzer/src/ai/prompts.py` — Phase별 프롬프트 상수

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `AIClient.__init__` | api_key, model 설정, openai 클라이언트 초기화 |
| `AIClient._call` | API 호출 공통 메서드 (재시도 3회, 지수 백오프) |
| `AIClient.generate_overview` | PRD.md + DESIGN.md 텍스트 반환 |
| `AIClient.analyze_class` | 주석 달린 소스코드 + 클래스 목적 한 줄 반환 |
| `AIClient.extract_semantic_nodes` | Node 목록(dict) 반환 |
| `AIClient.extract_semantic_edges` | Edge 목록(dict) 반환 |
| `prompts.py` | PROMPT_OVERVIEW, PROMPT_COMMENT, PROMPT_GRAPH_NODES, PROMPT_GRAPH_EDGES 상수 |

**코드 테스트** (`tests/test_ai_client.py`):
- `_call` 재시도 로직 (mock openai)
- 응답 파싱 정확도

**인간 테스트**:
- 실제 API 키로 `generate_overview` 호출 → 텍스트 반환 확인
- `analyze_class` 호출 → 주석 포함 코드 반환 확인

---

### Session 2: File Scanner + Class Extractor (`core/`)

**상태**: 완료 ✅ (23/23 테스트 통과)  
**대상 파일**:
- `analyzer/src/core/file_scanner.py` — .py 파일 탐색 + 내용 집계 + 토큰 관리
- `analyzer/src/core/class_extractor.py` — Python AST 기반 클래스 추출 + ClassInfo 생성

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `FileScanner.scan(path)` | 디렉토리 재귀 탐색, .py 파일 목록 + 내용 반환 |
| `FileScanner.get_summary(path)` | 80K 토큰 초과 시 각 파일 첫 50줄 + 함수 시그니처만 반환 |
| `ClassInfo` dataclass | name, file_path, line_number, methods, base_classes, source_code |
| `ClassExtractor.extract(path)` | 모든 .py 파일 AST 파싱 → ClassInfo 목록 반환 |
| `ClassExtractor._parse_file` | 단일 파일 파싱 (SyntaxError 시 스킵 + 경고) |

**코드 테스트** (`tests/test_file_scanner.py`, `tests/test_class_extractor.py`):
- 파일 탐색 정확도 (tmp 디렉토리 사용)
- AST 파싱: 클래스명·메서드·기반클래스 추출 정확도
- SyntaxError 있는 파일 스킵 처리

**인간 테스트**:
- 실제 Python 프로젝트 경로 입력 → ClassInfo 목록 출력 확인

### Session 3: Dependency Analyzer (`core/`)

**상태**: 완료 ✅ (22/22 테스트 통과)  
**대상 파일**:
- `analyzer/src/core/dependency_analyzer.py` — 클래스 의존성 분석 + 위상 정렬

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `DependencyAnalyzer.build_graph(classes)` | ClassInfo 목록에서 `{클래스명: [의존 클래스명]}` 딕셔너리 생성 |
| `DependencyAnalyzer.sort(classes)` | 위상 정렬(Kahn's algorithm) → 정렬된 ClassInfo 목록 반환 |
| `DependencyAnalyzer.verify(classes, ordered)` | CLASS.md 전체 클래스 == CLASS_ORDER.md 클래스 검증, 누락 목록 반환 |
| `DependencyAnalyzer._find_references` | 단일 클래스 소스코드에서 타 클래스명 참조 탐색 (AST Name/Attribute) |
| 순환 의존성 처리 | 경고 후 나머지를 임의 순서로 추가 |

**코드 테스트** (`tests/test_dependency_analyzer.py`):
- 단순 의존성 정렬 (A→B, B→없음 → [B, A])
- 다단 의존성 (A→B→C → [C, B, A])
- 순환 의존성 경고 + 전체 클래스 포함 보장
- verify() 누락 감지

**인간 테스트**:
- 실제 프로젝트 ClassInfo 목록 입력 → 정렬 순서 육안 확인

### Session 4: Comment Injector (`core/`)

**상태**: 완료 ✅ (17/17 테스트 통과)  
**대상 파일**:
- `analyzer/src/core/comment_injector.py` — 원본 파일 백업 후 클래스 범위 주석 교체

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `CommentInjector.inject(class_info, commented_source)` | 원본 .bak 백업 → 클래스 범위 교체 → 문법 검증 → 실패 시 복구 |
| `CommentInjector.inject_many(pairs)` | 같은 파일 내 여러 클래스를 한 번에 처리 (중복 백업 방지) |
| `CommentInjector._replace_class_range` | line_start~line_end 범위를 commented_source로 교체 |
| `CommentInjector._backup` | `.bak` 파일 생성 |
| `CommentInjector._verify_syntax` | ast.parse로 삽입 후 문법 검증 |
| `CommentInjector._restore` | 문법 오류 시 .bak에서 원본 복구 |

**코드 테스트** (`tests/test_comment_injector.py`):
- 주석 삽입 후 파일 내용 정확히 교체됨
- 백업 파일(.bak) 생성 확인
- 주석 삽입 결과가 문법 오류면 원본 자동 복구
- 파일 앞/중간/끝 위치 클래스 모두 처리

**인간 테스트**:
- 실제 .py 파일에 주석 삽입 후 육안 확인 + `.bak` 존재 확인

### Session 5: Pipeline Orchestrator (`core/`)

**상태**: 완료 ✅ (13/13 테스트 통과)  
**대상 파일**:
- `analyzer/src/core/pipeline.py` — 5단계 파이프라인 조율 + progress.json 상태 관리

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `PipelineOrchestrator.__init__` | source_path, api_key, callback 초기화, output_dir 생성 |
| `run(resume)` | Phase 1~5 순차 실행. resume=True면 완료 Phase 스킵 |
| `_run_phase1` | FileScanner + AIClient.generate_overview → PRD.md + DESIGN.md |
| `_run_phase2` | ClassExtractor → CLASS.md |
| `_run_phase3` | DependencyAnalyzer → CLASS_ORDER.md |
| `_run_phase4` | 클래스별 CommentInjector + analysis.md 기록 (이어하기 지원) |
| `_run_phase5` | GraphGenerator 호출 → graph.json (Session 6 stub) |
| `_load/_save_progress` | progress.json 읽기/쓰기 |
| `_emit` | callback({event, data}) 호출 (None이면 무시) |

**이벤트 정의**:
- `phase_start` / `phase_done` / `class_done` / `pipeline_done` / `error`

**코드 테스트** (`tests/test_pipeline.py`):
- 정상 실행 시 Phase 1~5 순서 보장
- resume=True 시 완료 Phase 스킵
- Phase 4 클래스별 이어하기 (completed_classes)
- 콜백 이벤트 순서 검증
- 오류 발생 시 error 이벤트 + 예외 전파

### Session 6: Graph Generator (`graph/`)

**상태**: 완료 ✅ (22/22 테스트 통과)  
**대상 파일**:
- `analyzer/src/graph/__init__.py`
- `analyzer/src/graph/graph_generator.py` — analysis.md + 의존성 그래프 → graph.json

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `GraphGenerator.__init__(ai)` | AIClient 수신 |
| `GraphGenerator.generate(analysis, design, dep_graph)` | Node + Edge 추출 → `{nodes, edges, generated_at}` 반환 |
| `GraphGenerator._parse_analysis(content)` | `"ClassName : 목적"` 형식 파싱 → `{name: purpose}` dict |
| `GraphGenerator._filter_valid_edges(nodes, edges)` | Node 목록에 없는 source/target 포함 Edge 제거 |
| graph.json 스키마 | `{generated_at, nodes:[{id,label,purpose}], edges:[{source,target,relation}]}` |

**Pipeline 연동**: Session 5의 Phase 5 stub이 이제 실제로 동작함

**코드 테스트** (`tests/test_graph_generator.py`):
- `_parse_analysis` 정확도 (정상/빈/잘못된 형식)
- `generate()` 스키마 검증 (nodes/edges 키 존재)
- 유효하지 않은 Edge 필터링
- AIClient Mock으로 전체 흐름 검증

### Session 7: wxPython UI (`ui/`)

**상태**: 완료 ✅ (24/24 테스트 통과)  
**대상 파일**:
- `analyzer/src/ui/__init__.py`
- `analyzer/src/ui/main_window.py` — 메인 창 (경로 입력, 버튼, 레이아웃)
- `analyzer/src/ui/progress_panel.py` — 진행 패널 (게이지, 로그, 상태 레이블)

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `AnalyzerMainWindow` | wx.Frame 기반 메인 창, 소스 경로 + API 키 입력, 분석 시작/이어서 버튼 |
| `_run(resume)` | 별도 스레드에서 PipelineOrchestrator 실행 |
| `_pipeline_callback` | wx.CallAfter로 UI 스레드 안전 업데이트 |
| `ProgressPanel` | wx.Panel 기반 진행 패널 |
| `update_phase_start / done` | Phase 시작·완료 로그 추가 |
| `update_class_done` | 게이지 업데이트 + 클래스별 로그 |
| `update_pipeline_done` | 완료 메시지 |
| `update_error` | 에러 로그 (빨간색) |
| `append_log` | wx.CallAfter 안전 로그 추가 |

**코드 테스트** (`tests/test_ui.py`):
- wx 미설치 환경에서 pytest.importorskip('wx')로 자동 스킵
- wx 설치 환경: wx.App 생성 후 창 인스턴스화 + 이벤트 핸들러 호출 검증

**인간 테스트**:
- `python main.py` → 창 실행 확인
- 경로 선택 → 분석 시작 → 진행 로그 확인

### Session 8: Integration + main.py

**상태**: 완료 ✅ (15/15 테스트 통과)  
**대상 파일**:
- `analyzer/main.py` — wx.App 진입점, 환경변수 API 키 지원
- `analyzer/requirements.txt` — 최종 의존성 확정
- `analyzer/tests/test_integration.py` — 파이프라인 전체 흐름 통합 테스트

**구현 범위**:
| 항목 | 내용 |
|------|------|
| `main.py` | `wx.App` 생성 → `AnalyzerMainWindow` 실행, `OPENAI_API_KEY` 환경변수 자동 주입 |
| `requirements.txt` | `wxPython>=4.2.0`, `openai>=1.0.0` 확정 |
| `test_integration.py` | FileScanner→ClassExtractor→DependencyAnalyzer→CommentInjector→GraphGenerator 실제 파일 + Mock AI 전체 흐름 검증 |

**코드 테스트** (`tests/test_integration.py`):
- tmp_path에 샘플 Python 프로젝트 생성
- AIClient Mock으로 실제 API 호출 없이 PipelineOrchestrator.run() 전체 실행
- 산출물 파일 존재 검증: PRD.md, DESIGN.md, CLASS.md, CLASS_ORDER.md, analysis.md, graph.json

**인간 테스트**:
- `python main.py` → 창 실행 확인
- 실제 경로 + API 키 입력 → 분석 시작 → 산출물 생성 확인
