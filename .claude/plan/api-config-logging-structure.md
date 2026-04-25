# Plan: API Contracts, Config, Logging, Folder Structure

Tasks 28–30 + folder restructure. Recommended execution order: 28-quick → 29 → 30 → 28-full → structure.

---

## Task 28: API Contract Drift (frontend ↔ backend)

### Problem
`frontend/src/api/types.ts:26-39` — `JobSummary` interface missing fields that `backend/routes/check.py:57` sends:
- `failed_sections_count: number` — **missing entirely**
- `artifact_dir: string` — should be `string | null` (backend: `Optional[str]`)

Also `/status/{job_id}` in `backend/routes/results.py` returns many more fields not typed on frontend — ok for now since not consumed.

### Phase A — Quick fix (30 min)
**File:** `frontend/src/api/types.ts`

Change `JobSummary`:
```typescript
export interface JobSummary {
  id: string;
  status: "pending" | "processing" | "done" | "error" | "cancelled";
  phase: string;
  docx_name: string;
  current_checkpoint_name: string;
  checkpoint_sub_current: number;
  checkpoint_sub_total: number;
  queue_position: number;
  submitted_at: number;
  finished_at: number | null;
  error: string | null;
  artifact_dir: string | null;           // was: string
  failed_sections_count: number;         // ADD
}
```

### Phase B — Proper shared schema (6–12 h)

**Step 1** — Add Pydantic response models to backend:
- `backend/routes/check.py` — add `class JobSummaryResponse(BaseModel)` with all fields
- Use `response_model=list[JobSummaryResponse]` on `GET /jobs`
- Same for `/status/{job_id}` → `JobStatusResponse(BaseModel)`
- FastAPI auto-generates OpenAPI from Pydantic models

**Step 2** — Add codegen to frontend:
```bash
npm install -D openapi-typescript
```
Add npm script:
```json
"generate:api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/generated.ts"
```

**Step 3** — Replace manual `types.ts` with import from `generated.ts`:
```typescript
// src/api/types.ts becomes a re-export shim
export type { components } from "./generated";
export type JobSummary = components["schemas"]["JobSummaryResponse"];
```

**Step 4** — Add to CI / Makefile: run codegen, fail if diff (keeps contract in sync).

### Key files
| File | Operation | Detail |
|------|-----------|--------|
| `frontend/src/api/types.ts:26-39` | Modify | Add `failed_sections_count`, fix `artifact_dir` nullability |
| `backend/routes/check.py` | Modify | Add `JobSummaryResponse(BaseModel)`, `response_model=` |
| `backend/routes/results.py` | Modify | Add `JobStatusResponse(BaseModel)`, `response_model=` |
| `frontend/src/api/generated.ts` | Create | openapi-typescript output (generated, not hand-written) |
| `frontend/package.json` | Modify | Add `generate:api` script |

### Risk
Pydantic models must exactly match what `job_repo.py` returns — validate field by field against `jobs.py:Job` dataclass.

---

## Task 29: Config Single Source of Truth

### Problem
Two `.env.example` files with different vars, different defaults, different languages:

| Variable | root `.env.example` | `backend/.env.example` | Conflict |
|----------|---------------------|------------------------|----------|
| `OPENAI_MODEL` | `qwen3-coder-30b-a3b-instruct` | `qwen/qwen3-4b-2507` | different defaults |
| `AI_TIMEOUT` | present | **missing** | gap |
| `AI_CONNECT_TIMEOUT` | present | **missing** | gap |
| `DOC_CHUNK_SIZE` | present | **missing** | gap |
| `MAX_CHUNK_TOKENS` | present | **missing** | gap |
| `AI_CHUNK_MAX_TOKENS` | present | **missing** | gap |
| `PDF_PAGES_PER_CHUNK` | **missing** | present | gap |
| `MAX_FILE_SIZE_MB` | **missing** | present | gap |
| `RESULT_TTL_HOURS` | **missing** | present | gap |
| `CORS_ORIGINS` | **missing** | present | gap |
| comments language | English | Russian | mixed |

### Solution

**Design:** root `.env.example` = master for Docker deployment (most complete, English).
`backend/.env.example` = local Python dev shortcut that points to root.

**Step 1** — Add missing vars to root `.env.example`:
```
PDF_PAGES_PER_CHUNK=1
MAX_FILE_SIZE_MB=100
RESULT_TTL_HOURS=24
CORS_ORIGINS=http://localhost:5173,http://localhost:80
```
Use English comments throughout, align defaults.

**Step 2** — Rewrite `backend/.env.example`:
```
# Local development (direct Python/uvicorn, no Docker).
# For Docker deployment, see ../.env.example — that is the master reference.
#
# Minimum required for local dev:
OPENAI_API_KEY=lm-studio
OPENAI_BASE_URL=http://localhost:1234/v1
OPENAI_MODEL=your-model-id
```
Short, English, points to root.

**Step 3** — Update `README.md` config section: table of all vars, which file is master, when to use each.

**Step 4** — Verify `backend/settings.py` reads all vars (check `PDF_PAGES_PER_CHUNK`, `MAX_FILE_SIZE_MB` — may not be read currently).

### Key files
| File | Operation |
|------|-----------|
| `.env.example` | Add 4 missing vars, align OPENAI_MODEL default note |
| `backend/.env.example` | Rewrite as short local-dev shortcut in English |
| `README.md` | Add config reference table |
| `backend/settings.py` | Verify all vars are read |

---

## Task 30: Unified Logging + Error Codes

### Problem
Two distinct categories currently mixed:

1. **Internal log lines** (`logger.info/warning/error`) — already English in most files ✓
2. **HTTP error detail strings** (FastAPI `HTTPException.detail`) — Russian throughout routes

Russian HTTP details in:
- `routes/check.py`: "Сначала сохраните конфигурацию", "Задача не найдена"
- `routes/results.py`: "Задача не найдена" ×3, "Лог не найден" ×2, "Результат ещё не готов", "Файл результата не найден" ×2, "Файл Markdown не найден" ×2
- `validators.py`: "Доступ к файлу запрещён" ×2, "Файл не найден"
- `doc_parser.py:27`: Russian FileNotFoundError
- `routes/runtime.py`: "Файл промпта по умолчанию не найден"
- `main.py`: "Слишком много запросов" in rate-limit response
- `aggregator.py`: Russian in result text (user-visible output — intentional, skip)

### Solution

**Step 1** — Create `backend/error_codes.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ApiError:
    code: str
    detail_ru: str
    http_status: int

ERR_CONFIG_NOT_SET   = ApiError("ERR_CONFIG_NOT_SET",   "Конфигурация не задана", 400)
ERR_JOB_NOT_FOUND    = ApiError("ERR_JOB_NOT_FOUND",    "Задача не найдена", 404)
ERR_LOG_NOT_FOUND    = ApiError("ERR_LOG_NOT_FOUND",    "Лог не найден", 404)
ERR_RESULT_NOT_READY = ApiError("ERR_RESULT_NOT_READY", "Результат не готов", 400)
ERR_FILE_NOT_FOUND   = ApiError("ERR_FILE_NOT_FOUND",   "Файл не найден", 404)
ERR_ACCESS_DENIED    = ApiError("ERR_ACCESS_DENIED",    "Доступ запрещён", 403)
ERR_PROMPT_MISSING   = ApiError("ERR_PROMPT_MISSING",   "Файл промпта не найден", 500)
ERR_RATE_LIMITED     = ApiError("ERR_RATE_LIMITED",     "Слишком много запросов", 429)


def api_error(err: ApiError) -> HTTPException:
    return HTTPException(
        status_code=err.http_status,
        detail={"code": err.code, "message": err.detail_ru},
    )
```

**Step 2** — Replace raw `HTTPException(status_code=..., detail="...")` in all routes:
```python
# Before:
raise HTTPException(status_code=404, detail="Задача не найдена")
# After:
raise api_error(ERR_JOB_NOT_FOUND)
```

**Step 3** — Frontend handles structured detail:
```typescript
// frontend/src/api/jobs.ts
const d = await res.json().catch(() => ({})) as {
  detail?: { code?: string; message?: string } | string
};
const message = typeof d.detail === "object" ? d.detail?.message : d.detail;
throw new Error(message ?? `Error ${res.status}`);
```

**Step 4** — `doc_parser.py:27` — change to English (internal error):
```python
raise FileNotFoundError(f"File not found: {file_path}")
```

**Step 5** — Audit all `logger.*` calls across backend: must be English. Quick grep:
```bash
grep -rn 'logger\.' backend/*.py | grep -E '[А-Яа-я]'
```

### Key files
| File | Operation |
|------|-----------|
| `backend/error_codes.py` | Create — all error constants |
| `backend/routes/check.py` | Replace 3 raw HTTPExceptions |
| `backend/routes/results.py` | Replace 8 raw HTTPExceptions |
| `backend/routes/runtime.py` | Replace 1 raw HTTPException |
| `backend/validators.py` | Replace 2 raw HTTPExceptions |
| `backend/main.py` | Replace rate-limit response string |
| `backend/doc_parser.py:27` | English FileNotFoundError |
| `frontend/src/api/jobs.ts` | Handle structured `{code, message}` detail |

---

## Final Task: Folder Structure

### Problem
Backend has 29 Python files at flat root level. Frontend is well organized.

### Current → Proposed Backend Structure

```
backend/
  # NOW: 29 flat files + routes/ tests/ prompts/
  
  # PROPOSED:
  models/     jobs.py, doc_models.py
  services/   job_repo.py, queue_service.py, retention_service.py
  pipeline/   pipeline_orchestrator.py, pipeline_worker.py, aggregator.py, worker_servers.py
  ai/         ai_client.py, ai_config.py, text_ai_client.py, openai_sync_client.py, worker_ai_client.py
  parsing/    doc_parser.py, docling_client.py, md_cache.py, md_parser.py,
              range_parser.py, range_ai_validator.py, token_chunker.py
  config/     config_store.py, settings.py, path_mapper.py, path_mapping.json
  infra/      lifespan.py, rate_limit.py
  utils/      utils.py, validators.py, context_resolver.py
  routes/     (unchanged)
  tests/      (unchanged)
  prompts/    (unchanged)
  main.py     (stays at root — uvicorn entry point)
  error_codes.py  (from task 30)
```

### Implementation Steps

**Step 1** — Build import graph before touching anything:
```bash
grep -rn "^import\|^from" backend/*.py | grep -v __pycache__ > /tmp/import_graph.txt
```

**Step 2** — Create dirs + `__init__.py`:
```bash
mkdir -p backend/{models,services,pipeline,ai,parsing,config,infra,utils}
touch backend/{models,services,pipeline,ai,parsing,config,infra,utils}/__init__.py
```

**Step 3** — Move files one package at a time (smallest first to validate imports):
- Start: `models/` (jobs.py, doc_models.py) — fewest dependents
- Then: `config/` (settings.py, config_store.py)
- Then: `utils/` (utils.py, validators.py, context_resolver.py)
- Then: `parsing/`, `ai/`, `services/`, `pipeline/`

**Step 4** — After each package move, update imports in ALL files that reference moved modules. Pattern:
```python
# Before (bare import):
import job_repo
from jobs import Job, JobStatus

# After (package import):
from services import job_repo
from models.jobs import Job, JobStatus
```

**Step 5** — Update `backend/routes/*.py` — all use bare module imports.

**Step 6** — Update `backend/tests/*.py`.

**Step 7** — Check `backend/Dockerfile` CMD line — currently points at `main:app`. If main.py stays at root, no change needed.

**Step 8** — Run `mypy` + `pytest` after each package batch.

### Frontend — minor cleanup

Check if legacy components are imported anywhere:
```bash
grep -rn "PathField\|ProcessingView\|RangeField\|ResultView" frontend/src/
```
If unused: move to `frontend/src/components/_legacy/` or delete.

### Risk Assessment
| Risk | Mitigation |
|------|------------|
| Broken imports after restructure | Build import graph first, move one package at a time |
| Python path issues in Docker | Keep `main.py` at backend root, test Docker build |
| mypy can't find modules | Update `mypy.ini` `mypy_path` if needed |
| Circular imports exposed | Resolve before moving — restructure may reveal existing cycles |

---

## Execution Order

1. **Task 28 Phase A** (30 min) — Fix `types.ts`. Zero risk.
2. **Task 29** (2–3 h) — Config consolidation. Low risk.
3. **Task 30** (3–5 h) — Error codes. Medium risk — FE must handle both `string` and `{code, message}` detail during transition.
4. **Task 28 Phase B** (6–10 h) — OpenAPI codegen. Depends on task 30 Pydantic models.
5. **Folder structure** (6–10 h) — Highest risk, do last. Run tests after every package batch.

---

## SESSION_ID
- CODEX_SESSION: N/A
- GEMINI_SESSION: N/A
