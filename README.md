# Source Code Analyzer & Semantic Viewer

AI 기반 소스코드 분석 및 의미론적 시각화 도구 모음입니다.

## 프로젝트 구성

```
프로젝트/
├── analyzer/   # Tool 1 — Python + wxPython (V1)
└── viewer/     # Tool 2 — React + Vite + TS (V2)
```

---

## Tool 1: Source Code Analyzer (V1)

> **기술스택**: Python + wxPython + OpenAI GPT-4  
> **지원 언어**: Python / Java / C / C++ (`.py`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`)

소스코드 경로를 입력하면 AI가 자동으로 분석 문서를 생성하고, 코드에 주석을 삽입합니다.

### 동작 방식

1. 소스코드 경로를 앱에서 입력
2. AI가 전체 코드베이스를 파악 (Python/Java/C/C++ 혼합 프로젝트 지원)
3. 분석 문서 자동 생성 → 의존성 순서대로 주석 삽입

### 기능 1: 소스코드 분석 + 주석 달기

| 단계 | 출력물 | 설명 |
|------|--------|------|
| 1 | `PRD.md` | AI가 파악한 프로젝트 요구사항 |
| 2 | `DESIGN.md` | 아키텍처 및 구조 분석 |
| 3 | `CLASS.md` | 전체 클래스 목록 |
| 4 | `CLASS_ORDER.md` | 의존성 기반 분석 순서 (단순 → 복잡) |
| 5 | 소스코드 내 주석 | 함수 docstring + 내부 주석 |
| 6 | `analysis.md` | 클래스별 목적 요약 |

### 기능 2: 그래프 데이터 생성

분석 산출물을 기반으로 `graph.json`을 생성합니다:

- **Node**: 의미론적으로 핵심이 되는 컴포넌트
- **Edge**: Node 간 의미적 연결 관계 (한글 레이블)

---

## Tool 2: Semantic Graph Viewer (V2)

> **기술스택**: React + Vite + TypeScript

`graph.json`을 불러와 소스코드의 의미 구조를 그래프로 시각화합니다.

---

## 시작하기

### Analyzer 설치

```bash
cd analyzer
pip install -r requirements.txt

# API 키 설정 (.env 파일)
cp .env.example .env    # 또는 직접 .env 파일 생성
# OPENAI_API_KEY=sk-... 입력 후 저장

python main.py
```

### Viewer 설치 (V2)

```bash
cd viewer
npm install
npm run dev
```

---

## 개발 로드맵

- [x] 프로젝트 구조 설계
- [x] **V1**: Python/Java/C/C++ Analyzer + wxPython GUI
- [x] **V1**: 주석 자동 삽입 파이프라인 (5단계)
- [x] **V1**: Graph JSON 데이터 생성
- [ ] **V2**: React Graph Viewer
