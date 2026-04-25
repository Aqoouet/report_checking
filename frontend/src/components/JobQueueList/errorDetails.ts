import { ApiError } from "../../api";

export interface DisplayError {
  message: string;
  debugDetail: string;
}

export function formatDisplayError(error: unknown, fallback: string): DisplayError {
  if (error instanceof ApiError) {
    const parts = [`HTTP ${error.status}`, error.code];
    if (error.backendMessage) parts.push(error.backendMessage);
    return {
      message: error.message || fallback,
      debugDetail: parts.join(" | "),
    };
  }

  if (error instanceof Error) {
    return {
      message: fallback,
      debugDetail: error.name ? `${error.name}: ${error.message}` : error.message,
    };
  }

  if (typeof error === "string" && error.trim()) {
    return {
      message: fallback,
      debugDetail: error,
    };
  }

  return {
    message: fallback,
    debugDetail: "",
  };
}
