-- Task Flow 의 users · sessions · tasks 표 (PostgreSQL · Supabase)
-- SQLite 마이그레이션 0001~0004 를 적용한 최종 모양과 이름 · 필드가 같다.
-- 날짜는 SQLite 와 같이 글자(text)로 저장한다.
-- if not exists 라서 다시 실행해도 오류가 나지 않는다. 이미 있는 표의 열은 바꾸지 않는다.

create table if not exists users (
    id bigint generated always as identity primary key,
    username text not null unique,
    password_hash text not null
);

-- id 는 숫자 자동 증가가 아니다. 쿠키로 받은 값을 찾는 키이다. (DATA-MIGRATION-PLAN 3-2)
create table if not exists sessions (
    id text primary key,
    user_id bigint not null references users(id),
    expires_at text not null
);

create table if not exists tasks (
    id bigint generated always as identity primary key,
    title text not null check (length(trim(title)) > 0),
    description text not null default '',
    status text not null check (status in ('TODO', 'IN_PROGRESS', 'DONE')),
    created_at text not null,
    updated_at text not null,
    owner_id bigint not null references users(id),
    priority text not null default 'NORMAL' check (priority in ('LOW', 'NORMAL', 'HIGH')),
    -- SQLite 의 date() 대신 날짜로 바꿨다가 YYYY-MM-DD 로 다시 써서 비교한다.
    -- 없는 날짜(2026-02-30)는 검사 대신 날짜 변환 오류로 막힌다.
    due_date text check (due_date is null or to_char(due_date::date, 'YYYY-MM-DD') = due_date)
);

create index if not exists idx_tasks_owner_id on tasks(owner_id);

-- 정책은 만들지 않는다. anon · authenticated 는 아무 행도 못 본다. 표 주인은 RLS 를 건너뛴다.
alter table users enable row level security;
alter table sessions enable row level security;
alter table tasks enable row level security;
