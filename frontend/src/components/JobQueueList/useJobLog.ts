import { useEffect, useState } from "react";
import { fetchLog } from "../../api";
import { formatDisplayError, type DisplayError } from "./errorDetails";

export function useJobLog(jobId: string, active: boolean) {
  const [logText, setLogText] = useState("");
  const [logError, setLogError] = useState<DisplayError | null>(null);

  useEffect(() => {
    let mounted = true;
    if (!active) return () => { mounted = false; };
    const poll = () =>
      fetchLog(jobId)
        .then((t) => {
          if (mounted) {
            setLogText(t);
            setLogError(null);
          }
        })
        .catch((error: unknown) => {
          if (mounted) {
            setLogError(formatDisplayError(error, "Не удалось загрузить лог"));
          }
        });
    poll();
    const id = setInterval(poll, 2000);
    return () => { mounted = false; clearInterval(id); };
  }, [jobId, active]);

  return { logText, logError };
}
