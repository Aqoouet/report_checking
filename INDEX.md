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
- `backend/aggregator.py` — Builds final text report from checkpoint findings.
- `backend/ai_client.py` — OpenAI-compatible client wrapper for LLM checks and range validation.
- `backend/config_store.py` — In-memory pipeline config schema, parsing, and validation helpers.
- `backend/doc_models.py` — Dataclasses for parsed document structure (`DocData`, `Section`).
- `backend/doc_parser.py` — Unified DOCX parsing pipeline entrypoint returning `DocData` + Markdown.
- `backend/docling_client.py` — HTTP client for Docling conversion (`.docx` -> Markdown).
- `backend/jobs.py` — In-memory job queue/state model for pending/processing/done/error/cancelled tasks.
- `backend/main.py` — FastAPI app with `/config`, `/check`, `/jobs`, `/result_log`, queue worker loop, and path/output validation.
- `backend/md_cache.py` — SHA256-based Markdown cache for converted DOCX files.
- `backend/md_parser.py` — Splits Markdown into logical sections and applies range filtering.
- `backend/mypy.ini` — Type-checker configuration for backend Python code.
- `backend/path_mapper.py` — Maps Windows-style user paths to allowed Linux paths.
- `backend/path_mapping.json` — Mapping table/allowlist used by `path_mapper.py`.
- `backend/pipeline_orchestrator.py` — Multi-phase job pipeline (`convert/check/validate/summary`) with parallel worker-server checks and artifact logging.
- `backend/range_parser.py` — Regex-based quick parser for section range input.
- `backend/requirements-dev.txt` — Development dependencies (extends runtime requirements).
- `backend/requirements.txt` — Runtime Python dependencies.
- `backend/token_chunker.py` — Token-based chunking of long sections before LLM calls.

### Backend Checkpoints

- `backend/checkpoints/__init__.py` — Auto-discovers and instantiates `check_*.py` checkpoint classes.
- `backend/checkpoints/base.py` — Checkpoint base classes and per-section execution logic.
- `backend/checkpoints/check_clarity.py` — Clarity/style checkpoint implementation.

### Backend Prompts

- `backend/prompts/clarity.txt` — System prompt for clarity/scientific style evaluation.

## Frontend

- `frontend/.env.example` — Example `VITE_API_URL` value for dev mode.
- `frontend/.gitignore` — Frontend-local ignore patterns (node modules, logs, build output).
- `frontend/Dockerfile` — Multi-stage frontend build (Vite build -> nginx runtime).
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

- `frontend/src/App.tsx` — Main UI shell with "Настройки" dialog, "Проверить" action, and jobs section.
- `frontend/src/api.ts` — Typed API client for config, queue/jobs, logs, run, cancel, and download endpoints.
- `frontend/src/index.css` — Global styles for modal config editor, queue rows, status badges, and log panel.
- `frontend/src/main.tsx` — React app bootstrap and root render.

### Frontend Components

- `frontend/src/components/ConfigDialog.tsx` — YAML configuration editor with parameter docs and load/save file actions.
- `frontend/src/components/JobQueueList.tsx` — Polling queue view with phase/progress, cancel action, and live log toggle.
- `frontend/src/components/PathField.tsx` — Legacy path field component (kept in source).
- `frontend/src/components/ProcessingView.tsx` — Legacy processing state component (kept in source).
- `frontend/src/components/RangeField.tsx` — Legacy range field component (kept in source).
- `frontend/src/components/ResultView.tsx` — Legacy result state component (kept in source).

## Test Data

- `test_files/test.docx` — Sample DOCX document used for local/manual processing tests.

## Cursor/Debug Artifacts

- `.cursor/debug-380762.log` — Session debug log artifact generated during prior troubleshooting.
- `.cursor/debug-a54eed.log` — Session debug log artifact generated during prior troubleshooting.
