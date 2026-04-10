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
- `OPENAI_MODEL` — имя модели (узнать: `docker exec lmstudio lms ps`)
- `SYSTEM_PROMPT` — системный промпт для проверки отчётов
- `APP_PORT` — порт, на котором будет висеть UI (default: 5173)

## 3. Скачать и загрузить модель (если ещё не сделано)

```bash
# Скачать модель в контейнер LM Studio
docker exec lmstudio lms get qwen/qwen2.5-coder-32b --gguf -y

# Загрузить модель в сервер
docker exec lmstudio lms load qwen/qwen2.5-coder-32b
```

## 4. Запустить сервис

```bash
docker compose up --build -d
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
