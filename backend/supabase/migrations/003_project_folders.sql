-- MONV — Migration 003 : PROJETS (regroupement des conversations par projet).
-- À exécuter dans Supabase → SQL Editor après 001 et 002.

create table if not exists public.project_folders (
  id varchar(36) primary key,
  user_id varchar(36) not null references public.users (id) on delete cascade,
  name varchar(160) not null default 'Nouveau projet',
  sort_position integer not null default 0,
  created_at timestamptz not null default (now() at time zone 'utc'),
  updated_at timestamptz not null default (now() at time zone 'utc')
);

create index if not exists idx_project_folders_user_sort
  on public.project_folders (user_id, sort_position, updated_at desc);

alter table public.conversations
  add column if not exists folder_id varchar(36);

alter table public.conversations
  drop constraint if exists conversations_folder_id_fkey;

alter table public.conversations
  add constraint conversations_folder_id_fkey
  foreign key (folder_id) references public.project_folders (id) on delete set null;

create index if not exists idx_conversations_user_folder
  on public.conversations (user_id, folder_id);
