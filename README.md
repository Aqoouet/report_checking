# Report Checker

Сервис автоматической проверки PDF-отчётов с помощью нейросети. Нейросеть добавляет sticky note аннотации прямо в PDF-документ.

## Быстрый старт (Docker — рекомендуется)

Предполагается, что LM Studio уже запущен через Docker на порту `1234`
(из каталога `~/Desktop/LLM`).

```bash
cd report_checking

# 1. Скопируйте конфиг и заполните имя модели
cp .env.example .env
# Узнать имя загруженной модели:
#   docker exec lmstudio lms ps
# Вставьте его в OPENAI_MODEL=...

# 2. Соберите и запустите
docker compose up --build -d
```

Откройте http://localhost:5173

---

## Разработка без Docker

### 1. Бэкенд

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# В .env укажите OPENAI_BASE_URL=http://localhost:1234/v1

uvicorn main:app --reload --port 8000
```

### 2. Фронтенд

```bash
cd frontend
echo "VITE_API_URL=http://localhost:8000" > .env
npm install
npm run dev
```

Откройте http://localhost:5173

## Переменные окружения (backend/.env)

| Переменная | Описание | Значение по умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | Любая строка (LM Studio не проверяет) | `lm-studio` |
| `OPENAI_BASE_URL` | Адрес локального сервера LM Studio | `http://localhost:1234/v1` |
| `OPENAI_MODEL` | Имя модели из вкладки Local Server в LM Studio | `local-model` |
| `PROMPT_PRESET` | Имя файла в `backend/prompts/` без `.txt` (`default`, `formal`, `short`) | `default` |
| `SYSTEM_PROMPT_FILE` | Путь к своему `.txt` (перекрывает пресет) | — |
| `SYSTEM_PROMPT` | Запасной вариант, если файл пресета недоступен | короткий встроенный текст |

> **Совет:** имя модели в LM Studio видно в разделе **Developer → Local Server** рядом с кнопкой Start. Скопируйте его точно в `OPENAI_MODEL`.

## Как работает

1. Пользователь загружает PDF и указывает страницы для проверки (например `5-30`)
2. Бэкенд извлекает текст каждой страницы через PyMuPDF
3. Каждая страница последовательно отправляется нейросети с системным промптом
4. Ответ нейросети записывается как sticky note аннотация на соответствующую страницу
5. Пользователь скачивает PDF с комментариями — их видно в любом PDF-ридере
