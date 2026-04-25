# Запуск на боевом сервере

## 1. Клонировать репозиторий

```bash
git clone <repo-url> report_checking
cd report_checking
```

## 2. Настроить конфиг

```bash
cp .env.example .env
nano .env
```

Что заполнить:
- `OPENAI_MODEL` — модель для основных проверок.
- `OPENAI_VALIDATE_MODEL` — модель для валидации диапазона (`/validate_range`).
- `OPENAI_BASE_URL` — URL OpenAI-совместимого API (для LM Studio обычно `http://host.docker.internal:1234/v1`).
- `APP_PORT` — порт UI (по умолчанию `5173`).
- `HOST_STORAGE_U` и `HOST_STORAGE_P` — host-пути, которые backend монтирует как
  `/filer/users/rymax1e` и `/filer/wps/wp` соответственно (для `U:\` и `P:\` из `backend/app/path_mapping.json`)
- `BACKEND_UID` и `BACKEND_GID` — uid/gid пользователя в backend-контейнере.
  Для закрытых сетевых шар оставьте `0:0`, иначе получите `Permission denied` при валидации пути.

## 3. Скачать и загрузить модель (если ещё не сделано)

```bash
# Что уже есть на диске
docker exec lmstudio lms ls

# Загрузить модель (имя должно совпасть со строкой в lms ls)
docker exec lmstudio lms load qwen3.6-35b-a3b -y

# Убедиться, что модель в памяти и скопировать id в OPENAI_MODEL
docker exec lmstudio lms ps
curl -s http://localhost:1234/v1/models
```

Если нужной модели нет в `lms ls`, скачать, например:

```bash
docker exec lmstudio lms get qwen/qwen2.5-coder-32b --gguf -y
docker exec lmstudio lms load qwen/qwen2.5-coder-32b -y
```

## 4. Запустить сервис

```bash
docker compose up --build -d
```

Проверить, что сервисы поднялись:

```bash
docker compose ps
docker compose logs -f backend
```

Открыть: `http://<ip-сервера>:5173`

---

## Важно: поддерживаемый формат

Сейчас backend принимает только `.docx`.
Если передать другой формат, API вернет ошибку валидации пути.

---

## Диагностика ошибки «Нет доступа к файлу или каталогу»

1. Проверьте, что путь файла попадает в маппинг `backend/app/path_mapping.json`.
2. Убедитесь, что соответствующий host-каталог смонтирован (`HOST_STORAGE_U` / `HOST_STORAGE_P`).
3. Убедитесь, что mount backend не read-only (`docker inspect ... RW=true`).
4. Для сетевых шар с жесткими ACL используйте `BACKEND_UID=0`, `BACKEND_GID=0`.
5. После изменения `.env`/`docker-compose.yml` пересоздайте контейнеры:

```bash
docker compose down
docker compose up -d --build
```

---

## Полезные команды

```bash
# Посмотреть логи
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f docling

# Перезапустить после изменений в коде
docker compose up --build -d

# Остановить
docker compose down

# Проверить пользователя backend-контейнера (для прав доступа)
docker exec report-checker-backend id

# Проверить, что mount'ы видны внутри backend
docker inspect report-checker-backend --format '{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'

# Проверить что модель отвечает
curl http://localhost:1234/v1/models
```
