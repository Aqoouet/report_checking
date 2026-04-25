import { type JobSummary } from "../../api";
import type { DisplayError } from "./errorDetails";
import { JobRow } from "./JobRow";
import { useJobsPolling } from "./useJobsPolling";

const HIDE_AFTER_MS = 15 * 60 * 1000;
const TERMINAL: JobSummary["status"][] = ["done", "error", "cancelled"];

function ErrorBlock({ error }: { error: DisplayError }) {
  return (
    <div className="jobs-error">
      <div>{error.message}</div>
      {error.debugDetail && (
        <details>
          <summary>Подробности</summary>
          <code>{error.debugDetail}</code>
        </details>
      )}
    </div>
  );
}

export default function JobQueueList() {
  const { jobs, fetchError, now, deletedIds, markDeleted } = useJobsPolling();

  const visible = jobs.filter((j) => {
    if (deletedIds.has(j.id)) return false;
    if (!TERMINAL.includes(j.status)) return true;
    if (j.finished_at === null) return true;
    return now - j.finished_at * 1000 < HIDE_AFTER_MS;
  });

  if (fetchError && visible.length === 0) return <ErrorBlock error={fetchError} />;

  if (visible.length === 0) return <div className="jobs-empty">Нет задач</div>;

  return (
    <>
      {fetchError && <ErrorBlock error={fetchError} />}
      <div className="job-list">
        {visible.map((j) => (
          <JobRow
            key={j.id}
            job={j}
            onDelete={j.status === "pending" ? () => markDeleted(j.id) : undefined}
          />
        ))}
      </div>
    </>
  );
}
