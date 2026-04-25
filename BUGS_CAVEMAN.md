# РЕФАКТОР УЛЬТРА (КОДБАЗА ВСЯ)


2. `backend/validators.py` дубли allowlist-проверок (`validate_file_path`, `validate_output_dir`). FIXED in `5d6a269`: вынесен общий `_path_guard`. time to fix = done
3. `backend/validators.py` fail-open: пустой `path_mapping.json` => доступ ко всем путям. FIXED in `5d6a269`: сделан fail-close. time to fix = done
4. `backend/validators.py` path-check через `startswith` строкой. FIXED in `5d6a269`: переход на path-boundary (`is_relative_to`). time to fix = done

7. `backend/worker_servers.py` `get_worker_servers` без schema-check. Ввести pydantic-модель воркера. FIXED: добавлена `WorkerServer` pydantic-модель с валидацией url/concurrency, обновлены type hints в `pipeline_orchestrator.py`. time to fix = done
8. `backend/routes/check.py` + `backend/rate_limit.py`: `/check` берёт глобальный rate-limit по IP в памяти. Минимум: вынести в middleware + service, оставить in-memory. time to fix = 2-4h
9. `backend/routes/*`, `backend/pipeline_worker.py`, `backend/context_resolver.py`, `backend/ai_client.py` много `except Exception` глушат детали. Нужна типовая карта ошибок. time to fix = 3-6h
10. `backend/config_store.py` дубли валидации (preflight + validate_and_set). Один источник правил. time to fix = 2-4h
11. `backend/config_store.py` in-memory `_configs` без lock/TTL. Нужен thread-safe store + eviction. time to fix = 2-4h
13. `backend/jobs.py` смешан state + очередь + GC + файлы. Разделить на `JobRepo`, `QueueService`, `RetentionService`. time to fix = 6-10h
14. `backend/pipeline_orchestrator.py` длинный сценарий `run()` с 4 фазами в одной функции. Разбить на stage handlers. time to fix = 4-8h
15. `backend/pipeline_orchestrator.py` логгер сам пишет файл через `open`. Лучше stdlib logger + handler + context job_id. time to fix = 2-4h
16. `backend/pipeline_orchestrator.py` много прямых `get_job/update_job` в циклах. Сделать atomic progress API. time to fix = 3-6h
17. `backend/ai_client.py` sync OpenAI client + async httpx вызовы в одном модуле. Разделить client layers. time to fix = 3-6h
18. `backend/ai_client.py` parse JSON руками (`_parse_json`) хрупко. Ввести schema validation + strict response format. time to fix = 2-4h
19. `backend/token_chunker.py` глобальный `_MAX_TOKENS` читается при import. Делать runtime-config, не import-time side effect. time to fix = 1-2h
20. `backend/checkpoints/*` помечены LEGACY, но лежат в прод-коде. удалить. time to fix = 0.5-1h
21. `frontend/src/api.ts` слишком жирный god-file: session, DTO, fetchers, URL builders. Резать на `client/session/jobs/config`. time to fix = 3-6h
22. `frontend/src/api.ts` есть legacy `startCheck/pollStatus`, но UI живёт на `startCheckNew/fetchJobs`. Удалить мёртвые API. time to fix = 0.5-1h
23. `frontend/src/components/ConfigDialog.tsx` UI + YAML serialize/parse + docs в одном файле 400+ строк. Разделить hook/utils/view. time to fix = 4-8h
24. `frontend/src/components/ConfigDialog.tsx` `PARAM_DOCS` hardcode с бизнес-ограничениями. Вынести в schema-driven config docs. time to fix = 2-4h
25. `frontend/src/components/JobQueueList.tsx` polling/row/log/cancel всё смешано. Нужны `useJobsPolling`, `useJobLog`, dumb row. time to fix = 3-6h
26. `frontend/src/components/PathField.tsx`, `RangeField.tsx`, `ProcessingView.tsx`, `ResultView.tsx` legacy, в `App.tsx` не используются. Чистить. time to fix = 1-3h
28. Контракты API разъехались: frontend типы не покрывают `failed_sections_count`, backend отдает больше. Нужен shared schema/OpenAPI client. time to fix = 6-12h
29. Конфиги расползлись (`README`, `.env.example`, `backend/.env.example`) с разными дефолтами/терминами. Нужен один source-of-truth. time to fix = 2-4h
30. Логи/ошибки RU+EN вперемешку по слоям. Ввести единый стиль сообщений + error codes для UI. time to fix = 3-6h



1. `backend/main.py` монолит 650+ строк. FIXED в `72b87f6`: разнесено в `backend/routes/*`, `backend/validators.py`, `backend/pipeline_worker.py`, `backend/lifespan.py`. time to fix = done
5. `_RangeItem/_RangeSpec` в `backend/main.py` не используются. FIXED в `72b87f6`: удалено. time to fix = done
6. `_OUTPUT_BASE_DIR_STR` в `backend/main.py` не используется. FIXED в `72b87f6`: удалено. time to fix = done
