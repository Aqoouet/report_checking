import { useEffect, useState } from "react";
import { fetchLog } from "../../api";

export function useJobLog(jobId: string, active: boolean) {
  const [logText, setLogText] = useState("");

  useEffect(() => {
    if (!active) return;
    let mounted = true;
    const poll = () =>
      fetchLog(jobId)
        .then((t) => { if (mounted) setLogText(t); })
        .catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => { mounted = false; clearInterval(id); };
  }, [jobId, active]);

  return { logText };
}
