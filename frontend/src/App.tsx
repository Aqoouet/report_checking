import { useCallback, useEffect, useRef, useState } from "react";
import {
  pollStatus,
  resultUrl,
  startCheck,
  validateRange,
  type StatusResponse,
  type ValidateRangeResponse,
} from "./api";
import "./index.css";

type Stage = "idle" | "starting" | "processing" | "done" | "error";
type RangeState = "empty" | "validating" | "valid" | "invalid";

function detectFileType(path: string): "docx" | "pdf" | "" {
  const lower = path.toLowerCase().trim();
  if (lower.endsWith(".docx")) return "docx";
  if (lower.endsWith(".pdf")) return "pdf";
  return "";
}

function detectInputType(text: string): "sections" | "pages" | "" {
  const lower = text.toLowerCase();
  if (/страниц|стр\./.test(lower)) return "pages";
  if (/раздел/.test(lower)) return "sections";
  return "";
}

export default function App() {
  const [filePath, setFilePath] = useState("");
  const [rangeInput, setRangeInput] = useState("");
  const [rangeState, setRangeState] = useState<RangeState>("empty");
  const [rangeResult, setRangeResult] = useState<ValidateRangeResponse | null>(null);
  const [rangeError, setRangeError] = useState("");
  const [prevResultOpen, setPrevResultOpen] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<StatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fileType = detectFileType(filePath);

  // Warning when user specifies sections for PDF or pages for DOCX
  const inputType = detectInputType(rangeInput);
  const rangeTypeMismatch =
    rangeInput.trim() !== "" &&
    inputType !== "" &&
    fileType !== "" &&
    ((inputType === "sections" && fileType === "pdf") ||
      (inputType === "pages" && fileType === "docx"));

  const triggerValidation = useCallback(
    async (text: string, ft: string) => {
      if (!text.trim()) {
        setRangeState("empty");
        setRangeResult(null);
        setRangeError("");
        return;
      }
      if (!ft) {
        return;
      }
      setRangeState("validating");
      setRangeError("");
      try {
        const res = await validateRange(text, ft);
        setRangeResult(res);
        if (res.valid) {
          setRangeState("valid");
          setRangeError("");
        } else {
          setRangeState("invalid");
          setRangeError(
            res.suggestion
              ? `Неверный диапазон. Возможное исправление: ${res.suggestion}`
              : "Неверный диапазон",
          );
        }
      } catch {
        setRangeState("invalid");
        setRangeError("Ошибка при валидации диапазона");
      }
    },
    [],
  );

  // Debounced validation on range input change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!rangeInput.trim()) {
      setRangeState("empty");
      setRangeResult(null);
      setRangeError("");
      return;
    }
    debounceRef.current = setTimeout(() => {
      triggerValidation(rangeInput, fileType);
    }, 800);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [rangeInput, fileType, triggerValidation]);

  const canSubmit =
    filePath.trim() !== "" &&
    stage !== "starting" &&
    (rangeInput.trim() === "" || rangeState === "valid");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setStage("starting");
    setErrorMsg("");
    setPrevResultOpen(false);

    try {
      const { job_id } = await startCheck(
        filePath.trim(),
        rangeResult?.valid ? rangeResult : undefined,
      );
      setJobId(job_id);
      setStage("processing");
      pollLoop(job_id);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStage("error");
    }
  };

  const pollLoop = (id: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await pollStatus(id);
        setProgress(status);

        if (status.status === "done") {
          clearInterval(interval);
          setStage("done");
        } else if (status.status === "error") {
          clearInterval(interval);
          setErrorMsg(status.error ?? "Неизвестная ошибка");
          setStage("error");
        }
      } catch {
        clearInterval(interval);
        setErrorMsg("Потеряна связь с сервером");
        setStage("error");
      }
    }, 1500);
  };

  const reset = () => {
    setFilePath("");
    setRangeInput("");
    setRangeState("empty");
    setRangeResult(null);
    setRangeError("");
    setStage("idle");
    setJobId("");
    setProgress(null);
    setErrorMsg("");
    setPrevResultOpen(false);
  };

  const pct =
    progress && progress.total_checkpoints > 0
      ? progress.checkpoint_sub_total
        ? Math.round(
            ((progress.current_checkpoint +
              (progress.checkpoint_sub_current ?? 0) /
                progress.checkpoint_sub_total) /
              progress.total_checkpoints) *
              100,
          )
        : Math.round(
            (progress.current_checkpoint / progress.total_checkpoints) * 100,
          )
      : 0;

  const prevResult = progress?.previous_result ?? "";
  const currentSubName = progress?.checkpoint_sub_name ?? "";

  return (
    <div className="page">
      <div className="card">
        <h1 className="title">Проверка отчёта</h1>
        <p className="subtitle">
          Укажите путь к файлу отчёта (.docx или .pdf) — система запустит все
          проверки и сформирует текстовый отчёт об ошибках.
        </p>

        {stage === "idle" || stage === "starting" ? (
          <form onSubmit={handleSubmit} className="form">
            <div className="field">
              <label className="label" htmlFor="filepath">
                Путь к файлу
              </label>
              <input
                id="filepath"
                className="input"
                type="text"
                placeholder="Например: C:\Users\name\report.docx или /home/name/report.docx"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                required
                autoComplete="off"
                spellCheck={false}
              />
              <span className="hint">
                Поддерживаются Windows- и Linux-пути. Файл должен быть доступен серверу.
              </span>
            </div>

            <div className="field">
              <label className="label" htmlFor="range">
                Диапазон проверки{" "}
                <span className="label-optional">(необязательно)</span>
              </label>
              <div className="range-input-wrap">
                <input
                  id="range"
                  className={`input${rangeState === "valid" ? " input--valid" : ""}${rangeState === "invalid" ? " input--invalid" : ""}`}
                  type="text"
                  placeholder={
                    fileType === "pdf"
                      ? "страница 1–3, 7"
                      : "раздел 3.2 3.3–5"
                  }
                  value={rangeInput}
                  onChange={(e) => setRangeInput(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
                {rangeState === "validating" && (
                  <span className="range-spinner" title="Валидация…">⟳</span>
                )}
                {rangeState === "valid" && (
                  <span className="range-badge range-badge--ok">✓</span>
                )}
                {rangeState === "invalid" && (
                  <span className="range-badge range-badge--err">✕</span>
                )}
              </div>

              {rangeState === "valid" && rangeResult?.display && (
                <span className="range-display">{rangeResult.display}</span>
              )}
              {rangeState === "invalid" && rangeError && (
                <span className="range-error">{rangeError}</span>
              )}

              {rangeTypeMismatch && (
                <div className="warning">
                  {inputType === "sections" && fileType === "pdf"
                    ? "Для PDF-файлов рекомендуется указывать страницы, а не разделы."
                    : "Для DOCX-файлов рекомендуется указывать разделы, а не страницы."}
                </div>
              )}

              <span className="hint">
                Для .docx — разделы (раздел 3.1 3.2–3.5); для .pdf — страницы (страница 1–3, 7).
                Оставьте пустым для проверки всего документа.
              </span>
            </div>

            <button
              type="submit"
              className="btn btn--primary"
              disabled={!canSubmit}
            >
              {stage === "starting" ? "Запускаем…" : "Проверить"}
            </button>
          </form>
        ) : stage === "processing" ? (
          <div className="status-block">
            <div className="progress-label">
              {progress
                ? progress.current_checkpoint_short_name ||
                  progress.current_checkpoint_name ||
                  "Инициализация…"
                : "Инициализация…"}
            </div>

            {currentSubName && (
              <div className="progress-sub-name">{currentSubName}</div>
            )}

            <div className="progress-label progress-label--sub">
              {progress && progress.total_checkpoints > 0
                ? `Критерий ${progress.current_checkpoint + 1} из ${progress.total_checkpoints}${
                    progress.checkpoint_sub_location
                      ? ` · ${progress.checkpoint_sub_location}`
                      : ""
                  }`
                : ""}
            </div>

            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>

            {prevResult && (
              <div className="prev-result-block">
                <button
                  className="prev-result-toggle"
                  onClick={() => setPrevResultOpen((o) => !o)}
                  type="button"
                >
                  {prevResultOpen ? "▲" : "▼"} Результат предыдущей проверки
                </button>
                {prevResultOpen && (
                  <div className="prev-result-body">{prevResult}</div>
                )}
              </div>
            )}

            <p className="processing-note">
              Нейросеть выполняет проверки по очереди. Не закрывайте вкладку.
            </p>
          </div>
        ) : stage === "done" ? (
          <div className="status-block status-block--done">
            <div className="done-icon">✓</div>
            <p className="done-text">
              Проверено {progress?.total_checkpoints ?? ""} критери
              {progress?.total_checkpoints === 1 ? "й" : "ев"}. Отчёт готов.
            </p>
            <a
              href={resultUrl(jobId)}
              download="report_errors.txt"
              className="btn btn--primary"
            >
              Скачать отчёт об ошибках
            </a>
            <button className="btn btn--secondary" onClick={reset}>
              Проверить другой файл
            </button>
          </div>
        ) : (
          <div className="status-block status-block--error">
            <div className="error-icon">✕</div>
            <p className="error-text">{errorMsg}</p>
            <button className="btn btn--secondary" onClick={reset}>
              Попробовать снова
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
