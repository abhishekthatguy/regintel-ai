-- RegIntel profiles table — links Supabase auth users to employee records.
-- Run once on the dedicated RegIntel project (SQL editor or MCP apply_migration).
-- RLS: users can read their own profile; all writes go through our API with
-- the secret key (service role bypasses RLS) — users can never self-approve.

create table if not exists public.profiles (
    auth_user_id uuid primary key references auth.users(id) on delete cascade,
    email        text not null,
    name         text not null default '',
    employee_id  text,
    department   text not null default '',
    roles        jsonb not null default '["employee"]',
    approved     boolean not null default false,
    created_at   timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: read own"
    on public.profiles for select
    to authenticated
    using ((select auth.uid()) = auth_user_id);

-- No insert/update/delete policies for authenticated — profile writes are
-- server-side only (assign-employee endpoint or scripts/supabase_link_user.py).
