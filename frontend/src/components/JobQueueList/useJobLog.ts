import { useCallback, useState } from "react";
import { fetchLog } from "../../api";
import { formatDisplayError, type DisplayError } from "./errorDetails";
import { usePolling } from "./usePolling";

export function useJobLog(jobId: string, active: boolean) {
  const [logText, setLogText] = useState("");
  const [logError, setLogError] = useState<DisplayError | null>(null);

  const poll = useCallback(() => {
    fetchLog(jobId)
      .then((t) => {
        setLogText(t);
        setLogError(null);
      })
      .catch((error: unknown) => {
        setLogError(formatDisplayError(error, "Не удалось загрузить лог"));
      });
  }, [jobId]);

  usePolling(poll, 2000, active);

  return { logText, logError };
}
