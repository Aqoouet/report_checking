import { type JobSummary } from "../../api";
import { JobRow } from "./JobRow";
import { useJobsPolling } from "./useJobsPolling";

const HIDE_AFTER_MS = 15 * 60 * 1000;
const TERMINAL: JobSummary["status"][] = ["done", "error", "cancelled"];

export default function JobQueueList() {
  const { jobs, fetchError, now, deletedIds, markDeleted } = useJobsPolling();

  if (fetchError) return <div className="jobs-error">{fetchError}</div>;

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
          onDelete={j.status === "pending" ? () => markDeleted(j.id) : undefined}
        />
      ))}
    </div>
  );
}
