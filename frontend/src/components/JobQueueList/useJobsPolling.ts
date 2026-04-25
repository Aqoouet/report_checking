import { useEffect, useState } from "react";
import { fetchJobs, type JobSummary } from "../../api";

export function useJobsPolling() {
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

  const markDeleted = (id: string) =>
    setDeletedIds((prev) => new Set([...prev, id]));

  return { jobs, fetchError, now, deletedIds, markDeleted };
}
