# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Overseer is a reference architecture for a governed CI/CD control plane that puts AI
coding agents inside a pipeline with mandatory review, testing, security scanning, and
human approval before any deploy. It's a portfolio-grade MVP (not a hardened production
system — see "What's Real vs. Simplified in This MVP" in README.md), designed to run
entirely on local Docker with no cloud dependency.

The pipeline: `review → fix → test → security → approve → deploy`, implemented as a
LangGraph state machine in `orchestrator/graph.py`.

## Running the stack

There is no local dev server outside Docker — everything runs as Compose services.

```bash
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, POSTGRES_PASSWORD, WEBHOOK_SECRET

docker compose up -d postgres gitea registry
# open http://localhost:3000, create admin account, enable Actions in site config if desired

docker compose up -d --build orchestrator approval-ui

# In Gitea: Site Administration > Actions > Runners > generate a token, put it in .env as RUNNER_TOKEN
docker compose up -d runner
```

Rebuild a single service after code changes: `docker compose up -d --build orchestrator`
(or `approval-ui`). Tail logs with `docker compose logs -f orchestrator`.

Trigger a pipeline run by pushing a commit to a Gitea repo with a webhook configured to
`http://orchestrator:8000/webhook` (see README.md Quick Start for full webhook setup).
Approve/reject pending runs at `http://localhost:8501`.

Optional observability: `docker compose --profile observability up -d` (Langfuse; needs
`LANGFUSE_NEXTAUTH_SECRET`/`LANGFUSE_SALT`/`LANGFUSE_ENCRYPTION_KEY` in `.env`).

## Tests

`example-target-app/` is the demo target repo used to exercise the full pipeline — it
has a seeded bug (`app.py`'s `/divide` route has no zero-check) and a test
(`test_app.py`) that fails against it, so a run against it demonstrates the Fixer
actually patching code and Tester re-validating it.

Run its tests directly: `cd example-target-app && pytest -x --tb=short`

This is also literally the default command the `tester` node
(`orchestrator/nodes/tester.py`) runs against whatever repo it's pointed at —
`pytest -x --tb=short` unless the target repo has a `.overseer.yaml` at its
root setting `test_command` to something else (e.g. `npm test -- --ci`).
Falls back to the pytest default if that file is missing, unparseable, or
doesn't set `test_command`.

`orchestrator/tests/` has a small pytest suite for the orchestrator's own
logic: `test_graph.py` covers the four `route_after_*` routing functions in
`graph.py` (including the `max_fix_attempts` retry cap), and `test_tester.py`
covers the `.overseer.yaml` config-loading logic above. Run inside the built
image: `docker compose run --rm orchestrator pytest tests/ -v`.

## Architecture

### Container topology

Five core services (docker-compose.yml): `gitea` (source + webhooks), `orchestrator`
(FastAPI + LangGraph + CrewAI + Claude Code), `postgres` (run state + approvals),
`registry` (local image store), `approval-ui` (Streamlit). `runner` (Gitea Actions) and
`langfuse` are optional add-ons, not required for the core loop.

The `orchestrator` and `runner` containers mount the host's Docker socket
(`/var/run/docker.sock`) so they can build/push/run containers on the host — this is a
known, called-out privilege-escalation surface acceptable only because this is a local
demo (see README "What's Real vs. Simplified").

### Request flow

1. `orchestrator/main.py` — FastAPI app. `/webhook` verifies the Gitea HMAC signature
   (`_verify_signature`, no-op if `WEBHOOK_SECRET` unset), shallow-clones the repo into
   `WORKSPACE_DIR/<run_id>` (`_clone_repo`), computes the triggering diff (`_get_diff`:
   `HEAD~1..HEAD`, falling back to `git show HEAD` for a repo's first commit), writes an
   initial `runs` row, and kicks off `_run_pipeline` as a FastAPI background task.
2. `_run_pipeline` builds the initial `PipelineState` and calls
   `overseer_graph.invoke(...)`, keyed by `thread_id=run_id` against an in-memory
   LangGraph `MemorySaver` checkpointer (state does *not* survive an orchestrator
   restart mid-run — see README "Going to Production" for the Postgres-checkpointer
   upgrade path).
3. On completion, the final state's terminal fields (`deployed` /
   `approved is False` / anything else) are mapped to a `status` and written back to the
   `runs` table via `db.update_run`.

### The graph (`orchestrator/graph.py` + `orchestrator/nodes/`)

One file per stage, each a pure function `(PipelineState) -> dict` that returns only the
state keys it updates (LangGraph merges them in):

- **`reviewer.py`** — CrewAI agent calling the Anthropic API directly (not Claude Code)
  since it's pure reasoning over a diff string, no file access needed. Expects strict
  JSON back (`{"issues_found": bool, "notes": str}`); if the model doesn't return
  parseable JSON, it **fails safe by routing to Fixer anyway** rather than silently
  skipping review.
- **`fixer.py`** — the only node that invokes real Claude Code (via
  `claude_code_runner.run_claude_code`), because it's the only step that needs
  repo-aware file edits. Receives review notes on the first pass, and additionally the
  last test failure output on retries. If `DIFF_ONLY_MODE` is set (`config.py`,
  default off), `_extract_changed_files` parses the triggering diff's `diff --git a/..
  b/..` lines and both names those files in the prompt and scopes `allowedTools`'
  `Edit` to just them (`Edit(path/to/file.py)` syntax) — `Bash`/`Read`/`Grep`/`Glob`
  stay unscoped, so this narrows accidental edits but is **not** a hard security
  boundary (Bash can still write anywhere). Falls back to the unscoped
  `Read,Edit,Bash,Grep,Glob` if the mode is off or the diff doesn't parse to any
  files.
- **`tester.py`** — shells out to `pytest -x --tb=short` in the cloned repo by default,
  or to whatever `test_command` a `.overseer.yaml` at the target repo's root specifies
  (parsed with `shlex.split`), letting non-Python target repos plug in their own test
  runner without editing this file.
- **`security.py`** — shells out to `bandit -r . -f json -ll` (medium+ severity only).
  **Fails closed**: if the scanner crashes or emits unparseable output, `security_passed`
  is `False`, not `True` — a broken scanner blocks the deploy rather than silently
  waving it through.
- **`approval.py`** — sets status to `awaiting_approval`, then **blocks the graph
  execution thread** polling Postgres every 5s until a human flips the row to
  `approved`/`rejected` via the Streamlit UI, or `APPROVAL_TIMEOUT_SECONDS` elapses (in
  which case it's treated as a rejection, not left open).
- **`deploy.py`** — `docker build` → `docker push` to the local registry → `docker
  compose up -d --build` inside the cloned repo. Assumes the target repo has its own
  `docker-compose.yml`/`Dockerfile` at its root (see `example-target-app/` for the
  minimal expected shape).

Routing functions (`route_after_review`, `route_after_test`, `route_after_security`,
`route_after_approval`) are plain functions over `PipelineState`, registered via
`graph.add_conditional_edges` — read these alongside `graph.py`'s module docstring
(an ASCII diagram of the full state machine) to trace any control-flow question.

All six node functions are decorated with Langfuse's `@observe()` (from the `langfuse`
package), named after their graph node (`review`, `fix`, `test`, `security`, `approval`,
`deploy`). `main.py:_run_pipeline` wraps the `overseer_graph.invoke(...)` call in
`propagate_attributes(session_id=run_id, ...)` so every node trace for a given run groups
under one Langfuse session instead of six disconnected traces. This is fully inert (no
network activity) only when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`
are all genuinely *unset* — verified the SDK logs a warning and no-ops in that case. An
*empty-string* env var (`LANGFUSE_PUBLIC_KEY=` present but blank) is not equivalent: the
SDK treats presence as "configured" and attempts real background export retries against
its default cloud host, failing with a harmless-but-noisy 401 (never blocks or throws —
export happens async). Since `docker-compose.yml`'s `env_file: .env` loads whatever's
uncommented in `.env`, `.env.example` ships all three Langfuse vars *commented out* by
default, not just blank, to actually get the clean-disabled path — uncomment all three
together only when running the `langfuse` compose service.

### Bounded-loop governance

The one thing this whole architecture exists to demonstrate: an agent that can't
converge is stopped, not left looping. `route_after_test` sends failing runs back to
`fix` only while `fix_attempts < max_fix_attempts` (default 3, `MAX_FIX_ATTEMPTS` env
var); once exhausted it routes straight to `END` as `failed`. There is no equivalent
retry loop anywhere else in the graph — review, security, and approval are each
single-shot per run.

### Claude Code invocation (`claude_code_runner.py`)

Thin subprocess wrapper around the Claude Code CLI's headless mode: `claude -p <prompt>
--output-format json --allowedTools Read,Edit,Bash,Grep,Glob --max-turns 8
--dangerously-skip-permissions`. The skip-permissions flag is only considered safe here
because it's scoped to the orchestrator container's isolated per-run workspace clone —
never lift this invocation pattern into a context with a wider filesystem mount. Uses
`ANTHROPIC_API_KEY` (not subscription OAuth) since Claude Code is embedded in a larger
orchestrated product here rather than run as a standalone interactive tool. Treats a
zero exit code with an empty/missing `result` field as a failure worth surfacing, not a
silent success.

### State shape (`orchestrator/state.py`)

`PipelineState` is the single TypedDict threaded through every node — if you add a new
node or field, it has to be added here first, then to the initial-state dict in
`main.py:_run_pipeline`, matching the `runs` table columns (`scripts/init_db.sql`) for
anything that needs to survive into Postgres/the approval UI.

### Approval UI (`approval-ui/app.py`)

Standalone Streamlit app, no shared code with the orchestrator — it duplicates the
Postgres connection/query logic rather than importing from `orchestrator/db.py` (they're
separate containers/images). Polls and re-renders every 5s (`time.sleep(5); st.rerun()`).
If you change the `runs` table schema, this file and `orchestrator/db.py` both need
updating in lockstep.
