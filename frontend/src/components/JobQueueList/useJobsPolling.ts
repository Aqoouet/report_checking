import { useEffect, useState } from "react";
import { fetchJobs, type JobSummary } from "../../api";
import { formatDisplayError, type DisplayError } from "./errorDetails";

export function useJobsPolling() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [fetchError, setFetchError] = useState<DisplayError | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let active = true;

    const poll = () => {
      fetchJobs()
        .then((list) => {
          if (active) {
            setJobs(list);
            setFetchError(null);
            setNow(Date.now());
          }
        })
        .catch((error: unknown) => {
          if (active) {
            setNow(Date.now());
            setFetchError(formatDisplayError(error, "Не удалось получить список задач"));
          }
        });
    };

    poll();
    const id = setInterval(poll, 3000);
    return () => { active = false; clearInterval(id); };
  }, []);

  const markDeleted = (id: string) =>
    setDeletedIds((prev) => new Set([...prev, id]));

  return { jobs, fetchError, now, deletedIds, markDeleted };
}
