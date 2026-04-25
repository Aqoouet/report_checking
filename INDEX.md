# Repository File Index

This index maps every file currently in the repository and explains its purpose.

## Root

- `.env.example` — Example environment variables for local/Docker deployment.
- `.gitignore` — Ignore rules for env files, caches, build artifacts, and logs.
- `DEPLOY.md` — Production deployment steps and operational commands.
- `README.md` — Main project documentation, architecture, and quick-start instructions.
- `docker-compose.yml` — Multi-service stack: Docling, backend API, frontend nginx app.
- `rebuild-back-front.sh` — Helper script to rebuild and restart backend/frontend services.

## Backend

- `backend/.env.example` — Backend-specific environment template.
- `backend/Dockerfile` — Backend image build and `uvicorn` runtime command.
- `backend/mypy.ini` — Type-checker configuration for backend Python code.
- `backend/requirements-dev.txt` — Development dependencies (extends runtime requirements).
- `backend/requirements.txt` — Runtime Python dependencies.

### Backend App (`backend/app/`)

- `backend/app/__init__.py` — Package init.
- `backend/app/aggregator.py` — Builds final text report from per-section check findings.
- `backend/app/ai_client.py` — OpenAI-compatible async client wrapper for LLM calls.
- `backend/app/ai_config.py` — AI model and endpoint configuration helpers.
- `backend/app/config_store.py` — In-memory pipeline config schema, parsing, and validation helpers.
- `backend/app/context_resolver.py` — Resolves model context window size via `/models` endpoint.
- `backend/app/doc_models.py` — Dataclasses for parsed document structure (`DocData`, `Section`).
- `backend/app/doc_parser.py` — Unified DOCX parsing pipeline entrypoint returning `DocData` + Markdown.
- `backend/app/docling_client.py` — HTTP client for Docling conversion (`.docx` → Markdown).
- `backend/app/error_codes.py` — Shared API error code constants and `api_error` helper.
- `backend/app/job_repo.py` — In-memory job store: create, get, update, and list jobs.
- `backend/app/jobs.py` — `Job` dataclass and `JobStatus` enum.
- `backend/app/lifespan.py` — FastAPI lifespan context manager (startup/shutdown hooks).
- `backend/app/main.py` — FastAPI app factory, router registration, and middleware.
- `backend/app/md_cache.py` — SHA256-based Markdown cache for converted DOCX files.
- `backend/app/md_parser.py` — Splits Markdown into logical sections and applies range filtering.
- `backend/app/openai_sync_client.py` — Synchronous OpenAI-compatible HTTP client.
- `backend/app/path_mapper.py` — Maps Windows-style user paths to allowed Linux paths.
- `backend/app/path_mapping.json` — Mapping table/allowlist used by `path_mapper.py`.
- `backend/app/pipeline_check.py` — Parallel section-check stage of the pipeline.
- `backend/app/pipeline_convert.py` — DOCX-to-Markdown conversion stage of the pipeline.
- `backend/app/pipeline_infra.py` — Shared pipeline infrastructure: `ArtifactLogger`, chunked LLM calls, cancel helpers.
- `backend/app/pipeline_orchestrator.py` — Top-level pipeline runner sequencing convert → check → validate → summary.
- `backend/app/pipeline_summary.py` — Summary generation stage of the pipeline.
- `backend/app/pipeline_validate.py` — Validation stage of the pipeline.
- `backend/app/pipeline_worker.py` — Background worker that dequeues jobs and runs the pipeline.
- `backend/app/queue_service.py` — Job queue management: enqueue, dequeue, and status queries.
- `backend/app/range_ai_validator.py` — AI-assisted section range format validation.
- `backend/app/range_parser.py` — Regex-based quick parser for section range input.
- `backend/app/rate_limit.py` — Per-endpoint rate limiting middleware.
- `backend/app/retention_service.py` — Artifact directory retention and cleanup scheduler.
- `backend/app/settings.py` — App-wide constants (default prompt paths, env var names).
- `backend/app/text_ai_client.py` — AI client specialized for plain-text generation tasks.
- `backend/app/token_chunker.py` — Token-based chunking of long sections before LLM calls.
- `backend/app/utils.py` — Utility helpers (prompt file loading, etc.).
- `backend/app/validators.py` — Request-level input validators (file path checks, etc.).
- `backend/app/worker_ai_client.py` — AI client routed through worker-server pool.
- `backend/app/worker_servers.py` — `WorkerServer` model and pool management.

### Backend Routes (`backend/app/routes/`)

- `backend/app/routes/__init__.py` — Router package init.
- `backend/app/routes/check.py` — `/check` endpoint: enqueue a new pipeline job.
- `backend/app/routes/config.py` — `/config` endpoints: save and retrieve pipeline config.
- `backend/app/routes/results.py` — `/jobs` and `/result_log` endpoints: job list, cancel, and log download.
- `backend/app/routes/runtime.py` — `/runtime_info` and `/default_prompts` endpoints.
- `backend/app/routes/validation.py` — `/validate_path` and `/validate_range` endpoints.

### Backend Prompts (`backend/app/prompts/`)

- `backend/app/prompts/clarity.txt` — System prompt for clarity/scientific style evaluation.
- `backend/app/prompts/summary.txt` — System prompt for report summary generation.
- `backend/app/prompts/units.txt` — System prompt for units/dimensions check.
- `backend/app/prompts/validation.txt` — System prompt for validation-stage review.

## Frontend

- `frontend/.env.example` — Example `VITE_API_URL` value for dev mode.
- `frontend/.gitignore` — Frontend-local ignore patterns (node modules, logs, build output).
- `frontend/Dockerfile` — Multi-stage frontend build (Vite build → nginx runtime).
- `frontend/README.md` — Minimal pointer to the root documentation.
- `frontend/eslint.config.js` — ESLint + TypeScript + React hooks/react-refresh rules.
- `frontend/index.html` — Vite HTML entrypoint and root mount node.
- `frontend/nginx.conf` — SPA serving config and `/api` reverse proxy to backend.
- `frontend/package-lock.json` — NPM lockfile pinning exact dependency tree.
- `frontend/package.json` — Frontend scripts and dependency declarations.
- `frontend/tsconfig.app.json` — TypeScript compiler options for browser app source.
- `frontend/tsconfig.json` — TS project references for app and node configs.
- `frontend/tsconfig.node.json` — TypeScript config for Vite/node-side files.
- `frontend/vite.config.ts` — Vite configuration with React plugin.

### Frontend Public Assets

- `frontend/public/icons.svg` — SVG sprite icon set included in frontend build.

### Frontend Source

- `frontend/src/App.tsx` — Main UI shell: settings dialog, run action, and jobs section.
- `frontend/src/index.css` — Global styles for modal config editor, queue rows, status badges, and log panel.
- `frontend/src/main.tsx` — React app bootstrap and root render.

### Frontend API (`frontend/src/api/`)

- `frontend/src/api/client.ts` — Base `fetch` wrapper with error handling and base URL config.
- `frontend/src/api/config.ts` — Config API: save, load, and fetch default prompts.
- `frontend/src/api/index.ts` — Re-exports all API functions as a single module entry point.
- `frontend/src/api/jobs.ts` — Jobs API: run, cancel, poll queue, and download result.
- `frontend/src/api/types.ts` — Shared TypeScript types for API request/response shapes.

### Frontend Components

- `frontend/src/components/ConfigDialog/index.tsx` — YAML configuration editor with parameter docs and load/save file actions.
- `frontend/src/components/ConfigDialog/paramDocs.ts` — Human-readable documentation strings for each config parameter.
- `frontend/src/components/ConfigDialog/useConfigDialog.ts` — State and logic hook for the config dialog.
- `frontend/src/components/ConfigDialog/yaml.ts` — YAML serialization/deserialization helpers for config values.
- `frontend/src/components/JobQueueList/index.tsx` — Polling queue view with phase/progress, cancel action, and live log toggle.
- `frontend/src/components/JobQueueList/JobRow.tsx` — Single job row with status badge, progress bar, and action buttons.
- `frontend/src/components/JobQueueList/errorDetails.ts` — Parses and formats structured error details from job state.
- `frontend/src/components/JobQueueList/useJobLog.ts` — Hook for fetching and displaying live job log output.
- `frontend/src/components/JobQueueList/useJobsPolling.ts` — Hook for polling the job queue at a fixed interval.

## Test Data

- `test_files/test.docx` — Sample DOCX document used for local/manual processing tests.

## Cursor/Debug Artifacts

- `.cursor/debug-380762.log` — Session debug log artifact generated during prior troubleshooting.
- `.cursor/debug-a54eed.log` — Session debug log artifact generated during prior troubleshooting.
