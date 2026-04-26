import { useEffect, useRef, useState } from "react";
import { cancelJob, type JobSummary } from "../../api";
import { Icon } from "../Icon";
import { formatDisplayError, type DisplayError } from "./errorDetails";
import { useJobLog } from "./useJobLog";

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

interface Props {
  job: JobSummary;
  onDelete?: () => void;
}

export function JobRow({ job, onDelete }: Props) {
  const isPending = job.status === "pending";
  const isProcessing = job.status === "processing";
  const isTerminal = job.status === "done" || job.status === "error" || job.status === "cancelled";
  const pct =
    job.checkpoint_sub_total > 0
      ? Math.round((job.checkpoint_sub_current / job.checkpoint_sub_total) * 100)
      : 0;

  const [logOpen, setLogOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [pendingCancel, setPendingCancel] = useState(false);
  const [cancelError, setCancelError] = useState<DisplayError | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  const { logText, logError } = useJobLog(job.id, isProcessing || pendingCancel);

  useEffect(() => {
    if (isTerminal) setPendingCancel(false);
  }, [isTerminal]);

  useEffect(() => {
    setCancelError(null);
  }, [job.id]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logText]);

  const handleCancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelJob(job.id);
      if (isPending) {
        onDelete?.();
      } else {
        setPendingCancel(true);
      }
    } catch (error) {
      setPendingCancel(false);
      setCancelError(formatDisplayError(error, "Не удалось отменить задачу"));
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className={`job-row job-row--${job.status}`}>
      <div className="job-row-header">
        <div className="job-docx-meta">
          <span className="job-docx-icon-wrap">
            <Icon name="i-document" className="job-docx-icon" />
          </span>
          <div className="job-docx-copy">
            <span className="job-docx-name" title={job.docx_name}>{job.docx_name || "—"}</span>
            <span className="job-time">{formatTime(job.submitted_at)}</span>
          </div>
        </div>
        <span className={`job-status ${STATUS_CLASS[job.status]}`}>{STATUS_LABEL[job.status]}</span>
      </div>

      {job.status === "pending" && job.queue_position > 0 && (
        <div className="job-queue-pos">
          <Icon name="i-clock" className="job-inline-icon" />
          <span>Позиция в очереди: {job.queue_position}</span>
        </div>
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

      {cancelError && (
        <div className="job-error-msg">
          <div>{cancelError.message}</div>
          {cancelError.debugDetail && (
            <details>
              <summary>Подробности отмены</summary>
              <code>{cancelError.debugDetail}</code>
            </details>
          )}
        </div>
      )}

      <div className="job-actions">
        {isPending && (
          <button
            type="button"
            className="btn btn--sm btn--danger"
            onClick={handleCancel}
            disabled={cancelling}
          >
            <Icon name="i-stop" className="btn__icon btn__icon--sm" />
            <span>{cancelling ? "Отменяем…" : "Отменить"}</span>
          </button>
        )}
        {(isProcessing || pendingCancel) && (
          <button
            type="button"
            className="btn btn--sm btn--danger"
            onClick={handleCancel}
            disabled={cancelling || pendingCancel}
          >
            <Icon name="i-stop" className="btn__icon btn__icon--sm" />
            <span>{cancelling ? "Останавливаем…" : pendingCancel ? "Отменяется…" : "Отменить"}</span>
          </button>
        )}
        {(isProcessing || pendingCancel) && (
          <button
            type="button"
            className="btn btn--sm btn--outline"
            onClick={() => setLogOpen((o) => !o)}
          >
            <Icon
              name={logOpen ? "i-chevron-down" : "i-terminal"}
              className="btn__icon btn__icon--sm"
            />
            <span>{logOpen ? "Скрыть лог" : "Показать лог"}</span>
          </button>
        )}
        {job.artifact_dir && (
          <div className="job-artifact-text">
            <Icon name="i-folder" className="job-inline-icon" />
            <span>Папка:</span>{" "}
            <a
              href={job.artifact_dir_file_url ?? undefined}
              className="job-artifact-link"
              title={job.artifact_dir_windows ?? job.artifact_dir}
            >
              {job.artifact_dir_windows ?? job.artifact_dir}
            </a>
          </div>
        )}
      </div>

      {(isProcessing || pendingCancel) && logOpen && (
        <>
          {logError && (
            <div className="job-error-msg">
              <div>{logError.message}</div>
              {logError.debugDetail && (
                <details>
                  <summary>Подробности лога</summary>
                  <code>{logError.debugDetail}</code>
                </details>
              )}
            </div>
          )}
          <pre ref={logRef} className="job-log-panel">
            {logText || "Лог пока пуст…"}
          </pre>
        </>
      )}
    </div>
  );
}
