# REFACTOR IDEAS CAVEMAN 2 (SORTED BY IMPORTANCE)

## MOST IMPORTANT (DO FIRST)

1. giant brain file: `backend/pipeline_orchestrator.py` hold too many phase + io + status update. split by stage handler. time to fix = 4-8h
4. queue state split brain: `backend/queue_service.py` + `backend/job_repo.py` both track queue-ish state (`_active_job_id`, `_waiting`, positions). centralize invariants. time to fix = 3-6h
6. api error format drift: some routes use `api_error(...)`, some throw plain `HTTPException`. align in `backend/routes/config.py`, `validation.py`, `results.py`. time to fix = 3-6h
11. silent fail in ui: empty `catch {}` in `frontend/src/components/JobQueueList/JobRow.tsx` and polling hooks hide real errors. surface user-safe error + debug detail. time to fix = 1-3h
13. yaml parse too forgiving: `frontend/src/components/ConfigDialog/yaml.ts` silently fallback defaults on bad values. show field-level validation errors instead. time to fix = 2-4h

## MEDIUM IMPORTANT

7. file write scatter: `backend/pipeline_orchestrator.py` + `backend/aggregator.py` do raw `open/write_text` all over. move to one artifact writer service. time to fix = 2-4h
8. infra hardcode in code: `backend/worker_servers.py` keep default IP list in source. move default to env/config file only. time to fix = 1-2h
10. frontend polling duplicated: `frontend/src/components/JobQueueList/useJobsPolling.ts` and `useJobLog.ts` repeat timer/error logic. extract common polling helper. time to fix = 2-4h
12. browser link brittle: `frontend/src/components/JobQueueList/JobRow.tsx` uses `file://` for artifact dir. browser may block. use backend download/open endpoint. time to fix = 1-2h

## NOT VERY IMPORTANT (CAN WAIT)

2. dead function smell: `backend/config_store.py` has `validate_preflight()` but nobody call. remove or wire real use. time to fix = 1-2h
3. private leak bad: `backend/routes/runtime.py` call `config_store._max_chunk_tokens()` private func. make public api in `config_store.py`. time to fix = 0.5-1h
14. docs drift from code: `INDEX.md` still list removed `frontend/src/api.ts` and old components. update map to real tree (`frontend/src/api/*`, new component paths). time to fix = 1-2h
