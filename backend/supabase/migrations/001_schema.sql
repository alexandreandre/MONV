-- MONV — schéma PostgreSQL à exécuter une fois dans Supabase → SQL Editor
-- Le backend utilise PostgREST avec la clé service_role (pas de DATABASE_URL).

create table if not exists public.users (
  id varchar(36) primary key,
  email varchar(255) not null unique,
  name varchar(255) not null,
  hashed_password varchar(255) not null,
  credits integer not null default 5,
  created_at timestamptz not null default (now() at time zone 'utc')
);

create table if not exists public.conversations (
  id varchar(36) primary key,
  user_id varchar(36) not null references public.users (id) on delete cascade,
  title varchar(255) not null default 'Nouvelle recherche',
  created_at timestamptz not null default (now() at time zone 'utc'),
  updated_at timestamptz not null default (now() at time zone 'utc')
);

create index if not exists idx_conversations_user on public.conversations (user_id);

create table if not exists public.messages (
  id varchar(36) primary key,
  conversation_id varchar(36) not null references public.conversations (id) on delete cascade,
  role varchar(20) not null,
  content text not null,
  message_type varchar(30) not null default 'text',
  metadata_json text,
  created_at timestamptz not null default (now() at time zone 'utc')
);

create index if not exists idx_messages_conversation on public.messages (conversation_id);

create table if not exists public.search_history (
  id varchar(36) primary key,
  user_id varchar(36) not null references public.users (id) on delete cascade,
  conversation_id varchar(36),
  query_text text not null,
  intent varchar(50) not null,
  entities_json text,
  results_count integer not null default 0,
  credits_used integer not null default 0,
  results_json text,
  exported boolean not null default false,
  export_path varchar(500),
  created_at timestamptz not null default (now() at time zone 'utc')
);

create index if not exists idx_search_history_user on public.search_history (user_id);

create table if not exists public.cache (
  key varchar(500) primary key,
  value_json text not null,
  created_at timestamptz not null default (now() at time zone 'utc'),
  expires_at timestamptz not null
);
