## Handoff: team-plan → team-exec

- **Decided**: 4 independent tasks, 4 workers in parallel. Backend tasks (7,8) touch Python only; frontend tasks (10,12) touch TypeScript only — no file conflicts.
- **Rejected**: Sequential execution (unnecessary); merging tasks 7+8 (different abstractions); merging tasks 10+12 (different concerns).

### Task 7 — Artifact Writer Service
- **Scatter map** (all raw file writes across pipeline):
  - `pipeline_check.py:97` — `Path(path).write_text(...)` in `_write_check_result()`
  - `pipeline_validate.py:45` — `Path(validated_path).write_text(...)` in `_run_validate_stage()`
  - `pipeline_convert.py:52` — `Path(converted_path).write_text(...)` in `_run_convert_stage()`
  - `pipeline_infra.py` — `path.write_text(...)` in `_write_config_yaml()`
  - `aggregator.py` — `open(path, "w", ...)` in `_write()`, called by `aggregate()` and `write_summary()`
- **Plan**: Create `backend/app/artifact_writer.py` with `write_artifact(path, text, encoding="utf-8")`. Replace all 5 scatter points. Keep `ArtifactLogger` (FileHandler-based, separate concern).

### Task 8 — Remove hardcoded IPs
- **Scatter**: `backend/app/worker_servers.py` `_DEFAULT_SERVERS` list with hardcoded IPs.
- **Plan**: Delete `_DEFAULT_SERVERS`. `get_worker_servers()` returns `[]` when env var absent/invalid. Add to `.env.example`.

### Task 10 — Extract polling hook
- **Scatter**: `useJobsPolling.ts` (3000ms) and `useJobLog.ts` (2000ms) share identical timer/flag/cleanup pattern.
- **Plan**: Create `frontend/src/components/JobQueueList/usePolling.ts` with `usePolling(fetchFn, interval, enabled?)`. Refactor both hooks to use it.

### Task 12 — Fix file:// link
- **Scatter**: `JobRow.tsx:157` uses `file://${job.artifact_dir}` — browsers block this for web-served pages.
- **Plan**: Add `POST /open_artifact/{job_id}` in `backend/app/routes/results.py` using `subprocess` + `xdg-open`. Change `JobRow.tsx` to a button calling this endpoint.

- **Risks**: Task 12 endpoint uses server-side `xdg-open` (Linux). Task 8 empty fallback — devs must set env var.
- **Files**: None created yet.
- **Remaining**: All implementation.
