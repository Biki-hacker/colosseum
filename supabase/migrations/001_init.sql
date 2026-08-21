-- Colosseum schema (run once in the Supabase SQL editor)
-- Debates are created by the server via the service-role key; the anon key
-- may read debates/turns for the public arena view (RLS read policies).

create table if not exists public.debates (
  id         uuid primary key default gen_random_uuid(),
  topic      text not null,
  status     text not null default 'running'
             check (status in ('scheduled', 'running', 'completed', 'failed')),
  winner     text check (winner in ('optimist', 'pessimist', 'tie') or winner is null),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  ended_at   timestamptz
);

create index if not exists debates_created_at_idx on public.debates (created_at desc);

create table if not exists public.turns (
  id        bigint generated always as identity primary key,
  debate_id uuid not null references public.debates (id) on delete cascade,
  speaker   text not null check (speaker in ('optimist', 'pessimist')),
  text      text not null,
  tokens    int not null,
  position  int not null
);

create index if not exists turns_debate_id_idx on public.turns (debate_id, position);

alter table public.debates enable row level security;
alter table public.turns enable row level security;

create policy "debates_public_read" on public.debates
  for select using (true);

create policy "turns_public_read" on public.turns
  for select using (true);