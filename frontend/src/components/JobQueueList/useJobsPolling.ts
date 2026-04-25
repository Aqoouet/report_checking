import { useCallback, useState } from "react";
import { fetchJobs, type JobSummary } from "../../api";
import { formatDisplayError, type DisplayError } from "./errorDetails";
import { usePolling } from "./usePolling";

export function useJobsPolling() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [fetchError, setFetchError] = useState<DisplayError | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  const poll = useCallback(() => {
    fetchJobs()
      .then((list) => {
        setJobs(list);
        setFetchError(null);
        setNow(Date.now());
      })
      .catch((error: unknown) => {
        setNow(Date.now());
        setFetchError(formatDisplayError(error, "Не удалось получить список задач"));
      });
  }, []);

  usePolling(poll, 3000);

  const markDeleted = (id: string) =>
    setDeletedIds((prev) => new Set([...prev, id]));

  return { jobs, fetchError, now, deletedIds, markDeleted };
}
