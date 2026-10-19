# task-flow

할 일을 카드로 등록하고 상태를 한눈에 보는 Task 관리 웹 앱. 현재는 M0(프로젝트 기본 구조)까지만 있다.
설계는 PRD.md, ARCHITECTURE.md, DECISIONS.md 를 본다.

## 실행

필요한 것: uv, Node.js LTS

백엔드 (http://127.0.0.1:8000)
```
cd backend
uv run uvicorn app.main:app --reload
```

화면 (http://localhost:5173)
```
cd frontend
npm install
npm run dev
```
화면의 `/api/*` 요청은 백엔드로 전달된다. 화면에 "API 상태: ok" 가 보이면 연결된 것이다.
