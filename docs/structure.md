# Repository Structure

## Source Folders

- `backend/app/` contains the FastAPI application, pipeline orchestration,
  routes, runtime settings, prompts, and path mapping.
- `backend/app/routes/` contains HTTP route modules.
- `backend/tests/` contains backend regression tests.
- `frontend/src/` contains the React/Vite application.
- `frontend/src/api/` owns browser-side API calls and error-code mapping.
- `frontend/src/components/` owns UI components and hooks.

## Generated Or Local-Only Folders

These folders are not source structure and should stay out of commits:

- Python caches: `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`
- Python virtual environments: `.venv/`, `backend/.venv/`
- Frontend dependencies/build output: `frontend/node_modules/`, `frontend/dist/`
- Local environment files: `.env`, `backend/.env`

## Deferred Restructure

Do not combine broad backend package moves with config or error-contract changes.
If the backend still needs structural cleanup after this phase, do it separately
with import migration and full test/build verification.
