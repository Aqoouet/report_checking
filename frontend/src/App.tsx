import { useRef, useState } from "react";
import { pollStatus, resultUrl, uploadPdf, type StatusResponse } from "./api";
import "./index.css";

type Stage = "idle" | "uploading" | "processing" | "done" | "error";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [pages, setPages] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<StatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f?.type === "application/pdf") setFile(f);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !pages.trim()) return;

    setStage("uploading");
    setErrorMsg("");

    try {
      const { job_id } = await uploadPdf(file, pages.trim());
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
    setFile(null);
    setPages("");
    setStage("idle");
    setJobId("");
    setProgress(null);
    setErrorMsg("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const pct =
    progress && progress.total_pages > 0
      ? Math.round((progress.current_page / progress.total_pages) * 100)
      : 0;

  return (
    <div className="page">
      <div className="card">
        <h1 className="title">Проверка отчёта</h1>
        <p className="subtitle">
          Загрузите PDF-отчёт, укажите страницы для проверки — нейросеть добавит
          комментарии прямо в документ.
        </p>

        {stage === "idle" || stage === "uploading" ? (
          <form onSubmit={handleSubmit} className="form">
            <div
              className={`drop-zone ${file ? "drop-zone--active" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setFile(f);
                }}
              />
              {file ? (
                <div className="file-info">
                  <span className="file-icon">📄</span>
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">
                    {(file.size / 1024 / 1024).toFixed(2)} МБ
                  </span>
                </div>
              ) : (
                <div className="drop-hint">
                  <span className="drop-icon">⬆</span>
                  <span>Перетащите PDF или нажмите для выбора</span>
                </div>
              )}
            </div>

            <div className="field">
              <label className="label" htmlFor="pages">
                Страницы для проверки
              </label>
              <input
                id="pages"
                className="input"
                type="text"
                placeholder="Например: 5-30 или 1, 3, 10-25"
                value={pages}
                onChange={(e) => setPages(e.target.value)}
                required
              />
              <span className="hint">
                Укажите диапазон или перечень: <code>5-30</code>,{" "}
                <code>1, 3, 10-25</code>
              </span>
            </div>

            <button
              type="submit"
              className="btn btn--primary"
              disabled={!file || !pages.trim() || stage === "uploading"}
            >
              {stage === "uploading" ? "Загружаем…" : "Проверить"}
            </button>
          </form>
        ) : stage === "processing" ? (
          <div className="status-block">
            <div className="progress-label">
              {progress
                ? `Страница ${progress.current_page} из ${progress.total_pages}`
                : "Инициализация…"}
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="processing-note">
              Нейросеть проверяет каждую страницу по очереди. Не закрывайте
              вкладку.
            </p>
          </div>
        ) : stage === "done" ? (
          <div className="status-block status-block--done">
            <div className="done-icon">✓</div>
            <p className="done-text">
              Проверено {progress?.total_pages ?? ""} стр. Комментарии добавлены
              в документ.
            </p>
            <a
              href={resultUrl(jobId)}
              download="report_reviewed.pdf"
              className="btn btn--primary"
            >
              Скачать PDF с комментариями
            </a>
            <button className="btn btn--secondary" onClick={reset}>
              Проверить другой отчёт
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
