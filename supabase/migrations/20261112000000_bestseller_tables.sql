-- 주간 베스트셀러 데이터 저장용 테이블
-- snapshots        : 매주 수집 결과 전체(JSON). 사이트 화면이 가장 최신 1건을 읽어 간다.
-- bestseller_items : 같은 내용을 한 줄에 책 한 권씩 펼친 표. Supabase 대시보드에서 보기 쉽고 주차별 비교에 쓴다.

create table if not exists public.snapshots (
  id            bigint generated always as identity primary key,
  week_start    date        not null unique,          -- 그 주의 월요일(한국 시간)
  collected_at  timestamptz not null default now(),
  data          jsonb       not null
);

create table if not exists public.bestseller_items (
  id            bigint generated always as identity primary key,
  week_start    date        not null,
  source_id     text        not null,                 -- yes24, kyobo, ypbooks ...
  source_name   text        not null,
  country       text        not null,
  category      text        not null,                 -- self_help, kids, economy
  rank          int         not null,
  title         text        not null,
  subtitle      text,
  author        text,
  publisher     text,
  pub_date      text,
  price         text,
  rating        text,
  rating_max    int,
  image         text,
  link          text,
  collected_at  timestamptz not null default now(),
  unique (week_start, source_id, category, rank)
);

create index if not exists bestseller_items_week_idx on public.bestseller_items (week_start desc);

-- 보안: 누구나 '읽기'만 가능. 쓰기는 GitHub Actions가 가진 비밀 키(secret/service_role)로만 가능.
alter table public.snapshots        enable row level security;
alter table public.bestseller_items enable row level security;

drop policy if exists "누구나 읽기" on public.snapshots;
create policy "누구나 읽기" on public.snapshots
  for select to anon, authenticated using (true);

drop policy if exists "누구나 읽기" on public.bestseller_items;
create policy "누구나 읽기" on public.bestseller_items
  for select to anon, authenticated using (true);

grant select on public.snapshots, public.bestseller_items to anon, authenticated;
grant all    on public.snapshots, public.bestseller_items to service_role;
