-- MONV — Migration 002 : ajout du `mode` (4 modes d'usage : prospection,
-- fournisseurs, client, rachat). Nullable pour rester compatible avec les
-- conversations / recherches existantes (NULL = prospection implicite).

alter table public.conversations
  add column if not exists mode varchar(20);

alter table public.search_history
  add column if not exists mode varchar(20);

create index if not exists idx_conversations_mode on public.conversations (mode);
create index if not exists idx_search_history_mode on public.search_history (mode);
