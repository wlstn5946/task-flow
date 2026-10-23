## 개요
- 로그인을 추가하고, 각 사용자가 자기 Task 만 보고 고칠 수 있게 분리합니다.

Closes #6

## 변경 내용
- API: POST /api/auth/register · login · logout, GET /api/auth/me 추가.
  /api/tasks 의 GET·POST·PATCH·DELETE 는 로그인 필요(없으면 401), 남의 Task 는 404.
- 데이터: users · sessions 표 추가, tasks 에 owner_id(users.id 참조, NOT NULL) 추가.

## 확인한 것 — 데이터
- 이전 전후 Task 수는 동일하고, 주인 없는 Task 수는 0

## 확인한 것 — 분리 · 회귀
- A 가 B 의 Task 수정 → 404 / 로그아웃 뒤 목록 → 401 / 어제 시나리오 통과
