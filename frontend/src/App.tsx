import { useState } from "react";
import { pollStatus, resultUrl, startCheck, type StatusResponse } from "./api";
import "./index.css";

type Stage = "idle" | "starting" | "processing" | "done" | "error";

export default function App() {
  const [filePath, setFilePath] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<StatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!filePath.trim()) return;

    setStage("starting");
    setErrorMsg("");

    try {
      const { job_id } = await startCheck(filePath.trim());
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
    setStage("idle");
    setJobId("");
    setProgress(null);
    setErrorMsg("");
  };

  const pct =
    progress && progress.total_checkpoints > 0
      ? progress.checkpoint_sub_total
        ? Math.round(
            ((progress.current_checkpoint +
              (progress.checkpoint_sub_current ?? 0) /
                progress.checkpoint_sub_total) /
              progress.total_checkpoints) *
              100
          )
        : Math.round(
            (progress.current_checkpoint / progress.total_checkpoints) * 100
          )
      : 0;

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

            <button
              type="submit"
              className="btn btn--primary"
              disabled={!filePath.trim() || stage === "starting"}
            >
              {stage === "starting" ? "Запускаем…" : "Проверить"}
            </button>
          </form>
        ) : stage === "processing" ? (
          <div className="status-block">
            <div className="progress-label">
              {progress
                ? (progress.current_checkpoint_short_name || progress.current_checkpoint_name)
                  ? (progress.current_checkpoint_short_name || progress.current_checkpoint_name)
                  : "Инициализация…"
                : "Инициализация…"}
            </div>
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
