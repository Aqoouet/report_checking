# Report Checker

Сервис очередной проверки технических отчетов `.docx` через OpenAI-совместимые LLM endpoint'ы.  
Текущая версия работает через pipeline-оркестратор: конвертация в Markdown, параллельная проверка по воркерам, опциональная валидация и summary, с артефактами по каждой задаче.

## Что умеет сервис сейчас

- Принимает конфигурацию проверки через `YAML`-редактор в UI (диалог "Настройки").
- Валидирует `input_docx_path` и `output_dir` на бэкенде с учетом allowlist из `backend/app/path_mapping.json`.
- Ставит проверки в очередь и показывает список задач (`pending/processing/done/error/cancelled`).
- Выполняет pipeline по фазам:
  - `convert` -> `check` -> `validate` (опционально) -> `summary` (опционально).
- Выполняет проверку разделов параллельно по пулу LLM-серверов (`WORKER_SERVERS`).
- Позволяет отменять задачу в процессе.
- Для каждой задачи сохраняет артефакты в отдельной папке:
  - `converted.md`
  - `check_result.txt` (или `validated_result.txt`, если включена валидация)
  - `summary.txt` (если включен summary)
  - `run.log`

## Архитектура

- `frontend` — React/Vite UI с очередью задач, live-логом и YAML-конфигурацией.
- `backend` — FastAPI API + очередь задач + pipeline orchestration.
- `docling` — `docling-serve` для конвертации `.docx` в Markdown.
- `LLM endpoints` — внешние OpenAI-совместимые сервера (по умолчанию задаются в `WORKER_SERVERS` или через `OPENAI_BASE_URL` для вспомогательных вызовов).

## Быстрый старт (Docker)

```bash
cd report_checking
cp .env.example .env

# Опционально настройте:
# OPENAI_BASE_URL, OPENAI_API_KEY
# OPENAI_MODEL, OPENAI_VALIDATE_MODEL
# OUTPUT_BASE_DIR, WORKER_SERVERS
# HOST_STORAGE_U, HOST_STORAGE_P
# BACKEND_UID, BACKEND_GID

docker compose up --build -d
docker compose ps
```

UI: `http://localhost:5173`

## Как пользоваться

1. Откройте `Настройки`.
2. Заполните YAML минимумом:
   - `input_docx_path`
   - `output_dir`
   - `check_prompt`
3. Нажмите `Сохранить`.
4. Нажмите `Проверить` на главном экране.
5. Следите за прогрессом в блоке `Задачи`, при необходимости откройте live-лог и/или отмените задачу.
6. После завершения скачайте:
   - `Отчёт`
   - `MD`
   - `Лог`

## Ключевые переменные окружения

Canonical source of truth for Docker/deployment defaults is [.env.example](.env.example).
Service-local examples are overlays only:
[backend/.env.example](backend/.env.example) is for direct local `uvicorn` runs, and
[frontend/.env.example](frontend/.env.example) is for direct local Vite runs.

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | API key OpenAI-совместимого endpoint | `lm-studio` |
| `OPENAI_BASE_URL` | Базовый URL LLM API | `http://host.docker.internal:1234/v1` |
| `OPENAI_MODEL` | Модель основных проверок и runtime info | `qwen3-coder-30b-a3b-instruct` |
| `OPENAI_VALIDATE_MODEL` | Модель для AI-валидации диапазона | `qwen/qwen3-4b-2507` |
| `AI_TIMEOUT` | Таймаут запроса к модели, сек (`0` = без лимита) | `0` |
| `AI_CONNECT_TIMEOUT` | Таймаут подключения, сек | `15` |
| `DOC_CHUNK_SIZE` | Примерный token budget одного фрагмента текста | `10000` |
| `MAX_CHUNK_TOKENS` | Верхний предел `chunk_size_tokens`, который можно задать в UI | `3000` |
| `AI_CHUNK_MAX_TOKENS` | `max_tokens` для ответа модели на один chunk (`0` = не передавать) | `0` |
| `WORKER_SERVERS` | JSON-массив LLM-воркеров с `url` и `concurrency` | пусто (используются встроенные defaults) |
| `OUTPUT_BASE_DIR` | Базовая директория результатов в контейнере | `/output` |
| `APP_PORT` | Порт frontend | `5173` |
| `HOST_STORAGE_U` | Host-путь для маппинга `U:\` | `/filer/users/rymax1e` |
| `HOST_STORAGE_P` | Host-путь для маппинга `P:\` | `/filer/wps/wp` |
| `BACKEND_UID` | UID процесса backend | `0` |
| `BACKEND_GID` | GID процесса backend | `0` |
| `PDF_PAGES_PER_CHUNK` | Количество страниц PDF, объединяемых в один AI-запрос | `1` |
| `MAX_FILE_SIZE_MB` | Максимальный размер входного файла | `100` |
| `RESULT_TTL_HOURS` | Время хранения временных result-файлов | `24` |
| `CORS_ORIGINS` | Разрешённые origins для прямого backend-доступа | `http://localhost:5173,http://localhost:80` |

See [docs/configuration.md](docs/configuration.md) for ownership rules and local-development overlays.

## Примечания по доступам

Если `validate_path` возвращает ошибки доступа:

1. Проверьте правильность mount'ов `HOST_STORAGE_U` и `HOST_STORAGE_P`.
2. Проверьте, что mounts не в режиме read-only (`RW=true` в `docker inspect`), иначе backend не сможет создать папку артефактов и `run.log` в `output_dir`.
3. Для закрытых файловых шар используйте `BACKEND_UID=0`, `BACKEND_GID=0`.
4. Пересоздайте контейнеры:

```bash
docker compose down
docker compose up -d --build
```
