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
- `OPENAI_MODEL` — имя доступной модели qwen coder (узнать: `docker exec lmstudio lms ps`)
- `SYSTEM_PROMPT` — системный промпт для проверки отчётов
- `APP_PORT` — порт, на котором будет висеть UI (default: 5173)

## 3. Скачать и загрузить модель (если ещё не сделано)

```bash
# Что уже есть на диске
docker exec lmstudio lms ls

# Загрузить qwen coder (имя должно совпасть со строкой в lms ls, например)
docker exec lmstudio lms load qwen3-coder-30b-a3b-instruct -y

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

## Полезные команды

```bash
# Посмотреть логи
docker compose logs -f backend
docker compose logs -f frontend

# Перезапустить после изменений в коде
docker compose up --build -d

# Остановить
docker compose down

# Проверить что модель отвечает
curl http://localhost:1234/v1/models
```
