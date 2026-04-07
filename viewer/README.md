# Semantic Graph Viewer

AI 소스코드 분석기(`analyzer`)가 생성한 `graph.json`을 방향 그래프로 시각화하는 웹 앱입니다.

- 클래스 간 의존관계를 노드·엣지 그래프로 표시
- 노드 클릭 시 클래스 목적·연결 관계 상세 표시
- 순수 정적 앱 — 서버·API 키·인터넷 연결 불필요

---

## 사전 요구사항

| 항목 | 버전 |
|------|------|
| Node.js | 18 이상 |
| npm | 9 이상 (Node.js에 포함) |

---

## 로컬 개발 실행

```bash
# 의존성 설치 (최초 1회)
npm install

# 개발 서버 시작
npm run dev
# → http://localhost:5173 에서 확인
```

---

## 프로그램 테스트 방법

### 1. analyzer로 graph.json 생성

```bash
cd ../analyzer

# 의존성 설치 (최초 1회)
pip install -r requirements.txt

# .env에 OpenAI API 키 설정
echo "OPENAI_API_KEY=sk-..." > .env

# 분석 실행 (소스코드 경로 지정)
python main.py
```

분석 완료 후 산출물 위치:
```
{분석한_소스코드_경로}/_ai_analysis/graph.json
```

### 2. Viewer에서 graph.json 열기

1. 브라우저에서 `http://localhost:5173` 접속
2. `graph.json을 드래그하거나 [파일 선택] 버튼을 클릭하세요` 화면에서:
   - **드래그앤드롭**: `graph.json` 파일을 화면에 끌어다 놓기
   - **파일 선택**: 버튼 클릭 후 `graph.json` 선택
3. 그래프가 자동으로 렌더링됩니다

### 3. 그래프 조작

| 동작 | 방법 |
|------|------|
| 노드 상세 보기 | 노드 클릭 → 우측 패널에 목적·연결 관계 표시 |
| 캔버스 이동 | 빈 영역 드래그 |
| 줌 인/아웃 | 마우스 휠 또는 좌측 하단 Controls |
| 노드 위치 이동 | 노드 드래그 |
| 엣지 곡률 조절 | 엣지 위에 마우스 올린 후 중앙 점 드래그 |
| 전체 보기 | 좌측 하단 "fit view" 버튼 |

### 4. 샘플 데이터로 빠른 테스트

analyzer 없이도 테스트 가능합니다:

```bash
# public/sample-graph.json 사용
# 개발 서버 실행 후 아래 파일을 드래그앤드롭
viewer/public/sample-graph.json
```

### 5. 오류 메시지 대처

| 오류 메시지 | 원인 | 해결 |
|-------------|------|------|
| JSON 파일만 지원합니다 | `.json` 확장자 아닌 파일 | `.json` 파일 사용 |
| graph.json 형식이 올바르지 않습니다 | `nodes`·`edges` 배열 없음 | analyzer 재실행 |
| 노드에 id·label·purpose 필드가 필요합니다 | 노드 스키마 불일치 | analyzer 버전 확인 |
| 엣지에 source·target·relation 필드가 필요합니다 | 엣지 스키마 불일치 | analyzer 버전 확인 |
| 노드가 없습니다 | nodes 배열이 비어있음 | 소스코드 경로·언어 확인 |

---

## 빌드

```bash
npm run build
# → dist/ 폴더에 정적 파일 생성
```

빌드 결과물 미리보기:

```bash
npm run preview
# → http://localhost:4173
```

---

## 배포

### 방법 1: Netlify Drop (가장 빠름, 무료)

1. `npm run build` 실행
2. [netlify.com/drop](https://netlify.com/drop) 접속
3. `dist/` 폴더 전체를 브라우저에 드래그앤드롭
4. 즉시 공개 URL 발급됨 (계정 불필요)

### 방법 2: Vercel (무료, CLI)

```bash
npm install -g vercel
npm run build
vercel --prod
```

### 방법 3: GitHub Pages (무료, 저장소 연동)

1. `vite.config.ts`에서 `base` 주석 해제 후 저장소 이름 입력:
   ```typescript
   base: '/저장소이름/',
   ```
2. 빌드 및 배포:
   ```bash
   npm run build
   # dist/ 폴더를 gh-pages 브랜치에 푸시
   npx gh-pages -d dist
   ```
3. GitHub 저장소 Settings → Pages → Source: `gh-pages` 브랜치 선택

### 방법 4: 로컬 파일 서버 (팀 내부 공유)

```bash
npm run build
npx serve dist
# → http://localhost:3000
```

### 방법 5: 정적 파일 직접 제공 (nginx/Apache)

```bash
npm run build
# dist/ 폴더를 웹 서버 루트에 복사
```

nginx 설정 예시:
```nginx
location / {
    root /path/to/dist;
    try_files $uri $uri/ /index.html;
}
```

---

## 배포 주의사항

- **API 키 불필요**: 이 앱은 순수 클라이언트 사이드 앱입니다. `.env` 파일이나 서버 설정 없이 `dist/` 폴더만 호스팅하면 됩니다.
- **HTTPS 권장**: 브라우저 보안 정책상 로컬 파일(`file://`)로 열면 일부 기능이 제한될 수 있습니다. 항상 웹 서버(http/https)를 통해 제공하세요.
- **graph.json은 배포에 포함하지 않음**: 소스코드 분석 결과는 민감 정보를 포함할 수 있습니다. `dist/sample-graph.json`은 개발용 샘플입니다.
- **GitHub Pages base 경로**: 루트 도메인이 아닌 서브 경로에 배포할 경우 반드시 `vite.config.ts`의 `base` 설정이 필요합니다.

---

## 기술 스택

| 항목 | 버전 |
|------|------|
| React | 18.3 |
| TypeScript | 5.5 |
| Vite | 5.4 |
| @xyflow/react (React Flow) | 12.x |
| dagre (레이아웃 엔진) | 0.8.5 |

---

## graph.json 스키마

```json
{
  "generated_at": "2026-04-07T00:00:00",
  "nodes": [
    {
      "id": "ClassName",
      "label": "한글 레이블",
      "purpose": "이 클래스의 목적을 설명하는 한 문장"
    }
  ],
  "edges": [
    {
      "source": "ClassName",
      "target": "AnotherClass",
      "relation": "호출한다"
    }
  ]
}
```
