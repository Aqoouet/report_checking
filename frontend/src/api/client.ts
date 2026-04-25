export const BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface ApiErrorDetail {
  code: string;
  message: string;
}

const ERROR_MESSAGES: Record<string, string> = {
  ERR_CONFIG_NOT_SET: "Сначала сохраните настройки проверки.",
  ERR_INVALID_JSON: "Некорректный JSON в запросе.",
  ERR_INPUT_DOCX_REQUIRED: "Укажите путь к исходному .docx файлу.",
  ERR_OUTPUT_DIR_REQUIRED: "Укажите папку для результатов.",
  ERR_CONFIG_VALIDATION_FAILED: "Проверьте параметры конфигурации.",
  ERR_JOB_NOT_FOUND: "Задача не найдена.",
  ERR_LOG_NOT_FOUND: "Лог не найден.",
  ERR_RESULT_NOT_READY: "Результат ещё не готов.",
  ERR_FILE_NOT_FOUND: "Файл не найден.",
  ERR_ACCESS_DENIED: "Нет доступа к указанному пути.",
  ERR_PATH_DENIED: "Путь вне разрешённой директории.",
  ERR_PROMPT_MISSING: "Файл промпта не найден.",
  ERR_RATE_LIMITED: "Слишком много запросов. Попробуйте позже.",
  ERR_INVALID_FILE_TYPE: "Поддерживаются только файлы .docx.",
};

export class ApiError extends Error {
  code: string;
  status: number;
  backendMessage: string;

  constructor(detail: ApiErrorDetail, status: number) {
    super(ERROR_MESSAGES[detail.code] ?? `Ошибка API (${detail.code})`);
    this.name = "ApiError";
    this.code = detail.code;
    this.status = status;
    this.backendMessage = detail.message;
  }
}

function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ApiErrorDetail).code === "string" &&
    typeof (value as ApiErrorDetail).message === "string"
  );
}

export async function throwApiError(res: Response, fallback: string): Promise<never> {
  const data = (await res.json().catch(() => null)) as { detail?: unknown } | null;
  if (data && isApiErrorDetail(data.detail)) {
    throw new ApiError(data.detail, res.status);
  }
  if (typeof data?.detail === "string") {
    throw new Error(data.detail);
  }
  throw new Error(`${fallback}: ${res.status}`);
}

function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function getSessionId(): string {
  let id = localStorage.getItem("rc_session_id");
  if (!id) {
    id = generateUUID();
    localStorage.setItem("rc_session_id", id);
  }
  return id;
}
