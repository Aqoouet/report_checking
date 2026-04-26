// Ikar UI Kit — JobRow component
// Recreates frontend/src/components/JobQueueList/JobRow.tsx visually.

const STATUS_LABEL = {
  pending: "Очередь",
  processing: "Выполняется",
  done: "Готово",
  error: "Ошибка",
  cancelled: "Остановлен",
};

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

const JobRow = ({ job, onCancel }) => {
  const { useState } = React;
  const [logOpen, setLogOpen] = useState(false);
  const isProcessing = job.status === "processing";
  const isPending = job.status === "pending";
  const pct = job.total > 0 ? Math.round((job.current / job.total) * 100) : 0;

  return (
    <div className={`job-row job-row--${job.status}`}>
      <div className="job-row-header">
        <span className="job-docx-name" title={job.name}>{job.name}</span>
        <Pill status={job.status}>{STATUS_LABEL[job.status]}</Pill>
        <span className="job-time">{formatTime(job.submittedAt)}</span>
      </div>

      {isPending && job.queuePosition > 0 && (
        <div className="job-queue-pos">Позиция в очереди: {job.queuePosition}</div>
      )}

      {isProcessing && (
        <div className="job-progress">
          <div className="job-phase">{job.phase}</div>
          {job.total > 0 && (
            <>
              <ProgressBar pct={pct} />
              <div className="job-progress-count">{job.current} / {job.total}</div>
            </>
          )}
        </div>
      )}

      {job.status === "error" && job.error && (
        <div className="job-error-msg">{job.error}</div>
      )}

      <div className="job-actions">
        {(isPending || isProcessing) && (
          <Button variant="danger" size="sm" onClick={() => onCancel && onCancel(job.id)}>Отменить</Button>
        )}
        {isProcessing && (
          <Button variant="outline" size="sm" onClick={() => setLogOpen(o => !o)}>
            {logOpen ? "Скрыть лог" : "Показать лог"}
          </Button>
        )}
        {job.artifactDir && (
          <div className="job-artifact-text">
            Папка: <a className="job-artifact-link" href="#">{job.artifactDir}</a>
          </div>
        )}
      </div>

      {isProcessing && logOpen && (
        <pre className="job-log-panel">{job.log || "Лог пока пуст…"}</pre>
      )}
    </div>
  );
};

window.JobRow = JobRow;
