# Report Checker

Сервис автоматической проверки технических отчетов в формате `.docx` с помощью локальной LLM (LM Studio / OpenAI-совместимый API). Пользователь указывает путь к файлу на сервере, система валидирует доступ, выполняет проверки по чекпоинтам и формирует итоговый отчет.

## Что умеет сервис

- Проверяет только `.docx` (валидация пути и расширения на бэкенде).
- Прогоняет документ через чекпоинты (сейчас: ясность изложения, единицы измерения).
- Поддерживает выборочный запуск по диапазону разделов.
- Показывает прогресс в реальном времени и позволяет отменить выполнение.
- Отдает два результата:
  - текстовый отчет об ошибках (`report_errors.txt` или `report_errors_partial.txt`);
  - Markdown-представление документа (`*_docling.md`).

## Архитектура

- `frontend` — React/Vite интерфейс (nginx в Docker).
- `backend` — FastAPI оркестратор проверок и файловых результатов.
- `docling` — отдельный сервис `docling-serve` для конвертации `.docx` в Markdown.
- `LM Studio` — внешний для compose сервис на хосте (по умолчанию `http://host.docker.internal:1234/v1`).

## Быстрый старт (Docker)

Предполагается, что LM Studio уже запущен на хосте и модель загружена.

```bash
cd report_checking
cp .env.example .env

# При необходимости настройте:
# OPENAI_MODEL, OPENAI_VALIDATE_MODEL, APP_PORT
# HOST_STORAGE_U, HOST_STORAGE_P
# BACKEND_UID, BACKEND_GID

docker compose up --build -d
docker compose ps
```

Откройте: `http://localhost:5173`

## Важные переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | Ключ для OpenAI-совместимого API | `lm-studio` |
| `OPENAI_BASE_URL` | База API модели | `http://host.docker.internal:1234/v1` |
| `OPENAI_MODEL` | Модель для основных проверок | `qwen3.6-35b-a3b` |
| `OPENAI_VALIDATE_MODEL` | Модель для `/validate_range` | `qwen/qwen3-4b-2507` |
| `AI_TIMEOUT` | Таймаут ответа модели, сек (`0` = без лимита) | `0` |
| `AI_CONNECT_TIMEOUT` | Таймаут подключения к модели, сек | `15` |
| `DOC_CHUNK_SIZE` | Размер фрагмента текста для проверки | `10000` |
| `APP_PORT` | Порт UI | `5173` |
| `HOST_STORAGE_U` | Host-путь для маппинга `U:\` | `/filer/users/rymax1e` |
| `HOST_STORAGE_P` | Host-путь для маппинга `P:\` | `/filer/wps/wp` |
| `BACKEND_UID` | UID пользователя backend-контейнера | `0` |
| `BACKEND_GID` | GID пользователя backend-контейнера | `0` |

## Права доступа к файловым шарам

Если при валидации пути видите `Нет доступа к файлу или каталогу` / `Permission denied`:

1. Проверьте, что нужный host-каталог примонтирован в `backend` (`HOST_STORAGE_U` / `HOST_STORAGE_P`).
2. Для закрытых сетевых шар оставьте `BACKEND_UID=0`, `BACKEND_GID=0`.
3. Пересоздайте контейнеры:

```bash
docker compose down
docker compose up -d --build
```

## Поток обработки

1. Пользователь вводит путь к `.docx`.
2. Путь приводится через `backend/path_mapping.json` и проходит проверки безопасности (allowlist, symlink, доступ, существование).
3. Документ конвертируется в Markdown (Docling), Markdown кешируется.
4. Чекпоинты обрабатывают разделы (или выбранный диапазон).
5. Формируются и выдаются итоговые файлы результата.
