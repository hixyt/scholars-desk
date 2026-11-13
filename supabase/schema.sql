-- The Scholar's Desk: tables for the subscribe form and the claim checker.
-- Run it once in Supabase (SQL Editor, paste, Run). Running it again is safe and changes nothing.
--
-- Visitors never touch these tables directly. Only the "desk" Edge Function and the morning
-- run (for the subscribers list) can read or write them, using the secret key.
-- The Seal Book's own table (seals) is not touched here.

create table if not exists public.subscribers (
  id bigint generated always as identity primary key,
  email text not null unique,
  topics text[] not null default '{}',              -- topic slugs from config.yaml; empty means every topic
  token uuid not null unique default gen_random_uuid(),  -- goes in the confirm, change-topics and unsubscribe links
  confirmed boolean not null default false,          -- only confirmed people get the morning email
  created_at timestamptz not null default now(),
  confirmed_at timestamptz,
  confirm_sent_at timestamptz,                       -- so the confirm email isn't sent again and again
  constraint email_looks_real check (length(email) <= 254 and email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);

create table if not exists public.claim_checks (
  id text primary key,                               -- the short id in a share link
  cache_key text not null unique,                    -- same paper and same text: reuse the old answer
  paper_id text not null,
  paper_title text not null default '',
  input_text text not null,
  result jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.usage_log (       -- for the daily limits; holds a scrambled visitor id, never an IP
  id bigint generated always as identity primary key,
  kind text not null,                                -- 'check' or 'subscribe'
  visitor text not null,
  created_at timestamptz not null default now()
);
create index if not exists usage_log_kind_time on public.usage_log (kind, created_at);

-- Row level security on, and no policies on purpose: the public (publishable) key can't read
-- or change anything in these tables. The secret key skips these rules.
alter table public.subscribers enable row level security;
alter table public.claim_checks enable row level security;
alter table public.usage_log enable row level security;
revoke all on public.subscribers, public.claim_checks, public.usage_log from anon, authenticated;

-- Tidy up every night at 3:30 AM India time (22:00 UTC): sign-ups never confirmed within
-- a week, and usage rows older than a month. Shared claim checks stay, so their links keep working.
create extension if not exists pg_cron;
select cron.schedule(
  'scholars-desk-tidy',
  '0 22 * * *',
  $$
  delete from public.subscribers where not confirmed and created_at < now() - interval '7 days';
  delete from public.usage_log where created_at < now() - interval '30 days';
  $$
);
