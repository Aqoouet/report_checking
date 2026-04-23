# Orchestrator Pipeline + GUI v2 — Implementation Plan

## Architecture

```
GUI  ──► POST /config ──► ConfigStore (in-memory)
GUI  ──► POST /check  ──► asyncio.Queue ──► PipelineOrchestrator.run()
GUI  ──► GET  /jobs   ──► list of JobSummary (for queue display)
```

### Pipeline Stages

```
CONVERT → SPLIT → CHECK (parallel, N servers) → VALIDATE (optional) → SUMMARY (optional) → PERSIST
```

### Key Decisions

1. **asyncio + Semaphore** replaces RabbitMQ. Each worker server has `asyncio.Semaphore(concurrency)`.
   Chunks distributed round-robin: `server = servers[i % len(servers)]`.

2. **asyncio.Queue (FIFO)** — single-active pipeline. One report processes at a time; others wait.

3. **PipelineConfig dataclass** stored in-memory server-side. Set via `POST /config` (JSON body).
   Frontend parses YAML with js-yaml, sends JSON to backend.

4. **ArtifactLogger** writes timestamped lines to `run.log` in artifact folder.

5. **Per-run artifact folders**: `{output_dir}/{stem}_{YYYYMMDD_HHMMSS}/`
   Contents: `converted.md`, `check_result.txt`, `validated_result.txt` (optional),
   `summary.txt` (optional), `run.log`

6. **Optional stages**: validation and summary skipped when their prompt is empty string.

7. **Worker servers**: configured via `WORKER_SERVERS` JSON env var.
   Default: `[{"url": "http://10.99.66.97:1234", "concurrency": 3}, {"url": "http://10.99.66.212:1234", "concurrency": 3}]`
   (stress10=10.99.66.97, stress12=10.99.66.212)

8. **Temperature**: optional — `None` means omit from request body (server default applies).

9. **Token count display**: computed after SPLIT via `count_tokens()` from token_chunker.py.

10. **Backward compatibility**: orchestrator sets `job.result_path` and `job.current_checkpoint_name`
    so existing `/result/{id}`, `/result_md/{id}`, `/status/{id}` still work.

11. **chunk_size_tokens** in config is display-only; actual chunking uses `DOC_CHUNK_SIZE` env var.

12. **No PyYAML on backend**: frontend parses YAML with js-yaml, sends JSON to POST /config.

## New Files

- `backend/config_store.py` — PipelineConfig dataclass + in-memory singleton
- `backend/pipeline_orchestrator.py` — async pipeline with ArtifactLogger
- `frontend/src/components/ConfigDialog.tsx` — YAML config editor dialog
- `frontend/src/components/JobQueueList.tsx` — polling job queue list

## Modified Files

- `backend/ai_client.py` — add `call_async()` using httpx directly
- `backend/jobs.py` — new fields + asyncio queue functions
- `backend/aggregator.py` — add `write_summary()`
- `backend/main.py` — new endpoints, pipeline worker in lifespan
- `docker-compose.yml` — add OUTPUT_BASE_DIR + WORKER_SERVERS env vars
- `frontend/package.json` — add js-yaml + @types/js-yaml
- `frontend/src/api.ts` — new endpoint functions + types
- `frontend/src/App.tsx` — two-button layout
- `frontend/src/index.css` — styles for new components

## Server Config

```json
[
  {"url": "http://10.99.66.97:1234", "concurrency": 3},
  {"url": "http://10.99.66.212:1234", "concurrency": 3}
]
```

Endpoint: `{url}/v1/chat/completions`
Health: `{url}/v1/models`
Model name: `"local-model"` (llama.cpp accepts any string)
