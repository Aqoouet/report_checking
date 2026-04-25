export const BASE = import.meta.env.VITE_API_URL ?? "/api";

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
