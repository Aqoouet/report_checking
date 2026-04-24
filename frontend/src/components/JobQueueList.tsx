import { useEffect, useRef, useState } from "react";
import { cancelJob, fetchJobs, fetchLog, resultLogUrl, resultMdUrl, resultUrl, type JobSummary } from "../api";

const PHASE_LABEL: Record<string, string> = {
  cancelling: "Ожидаем ответы серверов…",
};

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

function JobRow({ job, onDelete }: { job: JobSummary; onDelete?: () => void }) {
  const isPending = job.status === "pending";
  const isProcessing = job.status === "processing";
  const isTerminal = job.status === "done" || job.status === "error" || job.status === "cancelled";
  const pct =
    job.checkpoint_sub_total > 0
      ? Math.round((job.checkpoint_sub_current / job.checkpoint_sub_total) * 100)
      : 0;

  const [logOpen, setLogOpen] = useState(false);
  const [logText, setLogText] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [pendingCancel, setPendingCancel] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (isTerminal) setPendingCancel(false);
  }, [isTerminal]);

  useEffect(() => {
    if (!isProcessing && !pendingCancel) return;
    let active = true;
    const poll = () =>
      fetchLog(job.id)
        .then((t: string) => { if (active) setLogText(t); })
        .catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => { active = false; clearInterval(id); };
  }, [job.id, isProcessing, pendingCancel]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logText]);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await cancelJob(job.id);
      if (isPending) {
        onDelete?.();
      } else {
        setPendingCancel(true);
      }
    } catch { }
    finally { setCancelling(false); }
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
          <div className="job-phase">{PHASE_LABEL[job.phase] ?? (job.phase || job.current_checkpoint_name)}</div>
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
        {isPending && (
          <button
            type="button"
            className="btn btn--sm btn--danger"
            onClick={handleCancel}
            disabled={cancelling}
          >
            {cancelling ? "Отменяем…" : "Отменить"}
          </button>
        )}
        {(isProcessing || pendingCancel) && (
          <button
            type="button"
            className="btn btn--sm btn--danger"
            onClick={handleCancel}
            disabled={cancelling || pendingCancel}
          >
            {cancelling ? "Останавливаем…" : pendingCancel ? "Отменяется…" : "Отменить"}
          </button>
        )}
        {(isProcessing || pendingCancel) && (
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

      {(isProcessing || pendingCancel) && logOpen && (
        <pre ref={logRef} className="job-log-panel">
          {logText || "Лог пока пуст…"}
        </pre>
      )}
    </div>
  );
}

const HIDE_AFTER_MS = 15 * 60 * 1000;

export default function JobQueueList() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [fetchError, setFetchError] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let active = true;

    const poll = () => {
      fetchJobs()
        .then((list) => { if (active) { setJobs(list); setNow(Date.now()); } })
        .catch(() => { if (active) setFetchError("Не удалось получить список задач"); });
    };

    poll();
    const id = setInterval(poll, 3000);
    return () => { active = false; clearInterval(id); };
  }, []);

  if (fetchError) return <div className="jobs-error">{fetchError}</div>;

  const TERMINAL: JobSummary["status"][] = ["done", "error", "cancelled"];
  const visible = jobs.filter((j) => {
    if (deletedIds.has(j.id)) return false;
    if (!TERMINAL.includes(j.status)) return true;
    if (j.finished_at === null) return true;
    return now - j.finished_at * 1000 < HIDE_AFTER_MS;
  });

  if (visible.length === 0) return <div className="jobs-empty">Нет задач</div>;

  return (
    <div className="job-list">
      {visible.map((j) => (
        <JobRow
          key={j.id}
          job={j}
          onDelete={j.status === "pending" ? () => setDeletedIds((prev) => new Set([...prev, j.id])) : undefined}
        />
      ))}
    </div>
  );
}
