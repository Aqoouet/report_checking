import { useEffect, useRef, useState } from "react";
import { cancelJob, fetchJobs, fetchLog, resultLogUrl, resultMdUrl, resultUrl, type JobSummary } from "../api";

const STATUS_LABEL: Record<JobSummary["status"], string> = {
  pending: "Очередь",
  processing: "Выполняется",
  done: "Готово",
  error: "Ошибка",
  cancelled: "Остановлен",
};

const STATUS_CLASS: Record<JobSummary["status"], string> = {
  pending: "job-status--pending",
  processing: "job-status--processing",
  done: "job-status--done",
  error: "job-status--error",
  cancelled: "job-status--cancelled",
};

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function JobRow({ job }: { job: JobSummary }) {
  const isProcessing = job.status === "processing";
  const isTerminal = job.status === "done" || job.status === "error" || job.status === "cancelled";
  const pct =
    job.checkpoint_sub_total > 0
      ? Math.round((job.checkpoint_sub_current / job.checkpoint_sub_total) * 100)
      : 0;

  const [logOpen, setLogOpen] = useState(false);
  const [logText, setLogText] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!isProcessing) return;
    let active = true;
    const poll = () =>
      fetchLog(job.id)
        .then((t) => { if (active) setLogText(t); })
        .catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => { active = false; clearInterval(id); };
  }, [job.id, isProcessing]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logText]);

  const handleCancel = async () => {
    setCancelling(true);
    try { await cancelJob(job.id); } catch { } finally { setCancelling(false); }
  };

  return (
    <div className={`job-row job-row--${job.status}`}>
      <div className="job-row-header">
        <span className="job-docx-name" title={job.docx_name}>{job.docx_name || "—"}</span>
        <span className={`job-status ${STATUS_CLASS[job.status]}`}>{STATUS_LABEL[job.status]}</span>
        <span className="job-time">{formatTime(job.submitted_at)}</span>
      </div>

      {job.status === "pending" && job.queue_position > 0 && (
        <div className="job-queue-pos">Позиция в очереди: {job.queue_position}</div>
      )}

      {isProcessing && (
        <div className="job-progress">
          <div className="job-phase">{job.phase || job.current_checkpoint_name}</div>
          {job.checkpoint_sub_total > 0 && (
            <>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${pct}%` }} />
              </div>
              <div className="job-progress-count">
                {job.checkpoint_sub_current} / {job.checkpoint_sub_total}
              </div>
            </>
          )}
        </div>
      )}

      {job.status === "error" && job.error && (
        <div className="job-error-msg">{job.error}</div>
      )}

      <div className="job-actions">
        {isProcessing && (
          <button
            type="button"
            className="btn btn--sm btn--danger"
            onClick={handleCancel}
            disabled={cancelling}
          >
            {cancelling ? "Останавливаем…" : "Отменить"}
          </button>
        )}
        {isProcessing && (
          <button
            type="button"
            className="btn btn--sm btn--outline"
            onClick={() => setLogOpen((o) => !o)}
          >
            {logOpen ? "Скрыть лог" : "Показать лог"}
          </button>
        )}
        {isTerminal && (
          <>
            {job.status !== "error" && (
              <a href={resultUrl(job.id)} download className="btn btn--primary btn--sm">
                Отчёт
              </a>
            )}
            {job.status !== "error" && (
              <a href={resultMdUrl(job.id)} download className="btn btn--secondary btn--sm">
                MD
              </a>
            )}
            <a href={resultLogUrl(job.id)} download className="btn btn--secondary btn--sm">
              Лог
            </a>
          </>
        )}
      </div>

      {isProcessing && logOpen && (
        <pre ref={logRef} className="job-log-panel">
          {logText || "Лог пока пуст…"}
        </pre>
      )}
    </div>
  );
}

export default function JobQueueList() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    let active = true;

    const poll = () => {
      fetchJobs()
        .then((list) => { if (active) setJobs(list); })
        .catch(() => { if (active) setFetchError("Не удалось получить список задач"); });
    };

    poll();
    const id = setInterval(poll, 3000);
    return () => { active = false; clearInterval(id); };
  }, []);

  if (fetchError) return <div className="jobs-error">{fetchError}</div>;
  if (jobs.length === 0) return <div className="jobs-empty">Нет задач</div>;

  return (
    <div className="job-list">
      {jobs.map((j) => <JobRow key={j.id} job={j} />)}
    </div>
  );
}
