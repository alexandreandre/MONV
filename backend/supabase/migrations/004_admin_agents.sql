-- Admin : versions d'overrides par agent, exécutions et étapes (observabilité / tests)
-- IDs varchar(36) alignés sur public.users / conversations.

CREATE TABLE IF NOT EXISTS public.agent_versions (
    id varchar(36) PRIMARY KEY,
    agent_id text NOT NULL,
    version_number integer NOT NULL,
    label text NOT NULL DEFAULT '',
    overrides_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by varchar(36) REFERENCES public.users (id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    is_active boolean NOT NULL DEFAULT false,
    parent_version_id varchar(36) REFERENCES public.agent_versions (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_versions_one_active_per_agent
    ON public.agent_versions (agent_id)
    WHERE is_active = true;

CREATE INDEX IF NOT EXISTS agent_versions_agent_created
    ON public.agent_versions (agent_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.agent_runs (
    id varchar(36) PRIMARY KEY,
    agent_id text NOT NULL,
    version_id varchar(36) REFERENCES public.agent_versions (id) ON DELETE SET NULL,
    user_id varchar(36) NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    triggered_from text NOT NULL DEFAULT 'admin_test',
    status text NOT NULL DEFAULT 'running',
    started_at timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    finished_at timestamptz,
    total_tokens_in integer NOT NULL DEFAULT 0,
    total_tokens_out integer NOT NULL DEFAULT 0,
    total_cost_usd numeric(14, 8) NOT NULL DEFAULT 0,
    latency_ms integer,
    error_message text,
    input_json jsonb
);

CREATE INDEX IF NOT EXISTS agent_runs_agent_started
    ON public.agent_runs (agent_id, started_at DESC);

CREATE INDEX IF NOT EXISTS agent_runs_user_started
    ON public.agent_runs (user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS public.agent_run_steps (
    id varchar(36) PRIMARY KEY,
    run_id varchar(36) NOT NULL REFERENCES public.agent_runs (id) ON DELETE CASCADE,
    block_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    finished_at timestamptz,
    model_used text,
    tokens_in integer NOT NULL DEFAULT 0,
    tokens_out integer NOT NULL DEFAULT 0,
    cost_usd numeric(14, 8) NOT NULL DEFAULT 0,
    latency_ms integer,
    status text NOT NULL DEFAULT 'completed',
    input_json jsonb,
    output_json jsonb,
    error_message text
);

CREATE INDEX IF NOT EXISTS agent_run_steps_run_block
    ON public.agent_run_steps (run_id, started_at);
