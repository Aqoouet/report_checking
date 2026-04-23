import { useState } from "react";
import { startCheckNew } from "./api";
import ConfigDialog from "./components/ConfigDialog";
import JobQueueList from "./components/JobQueueList";
import "./index.css";

export default function App() {
  const [configOpen, setConfigOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  const handleCheck = async () => {
    setStarting(true);
    setStartError("");
    try {
      await startCheckNew();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="page">
      <div className="card card--wide">
        <h1 className="title">Проверка отчёта</h1>

        <div className="action-row">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => setConfigOpen(true)}
          >
            Настройки
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleCheck}
            disabled={starting}
          >
            {starting ? "Запускаем…" : "Проверить"}
          </button>
        </div>

        {startError && <div className="start-error">{startError}</div>}

        <div className="jobs-section">
          <div className="jobs-section-title">Задачи</div>
          <JobQueueList />
        </div>
      </div>

      {configOpen && <ConfigDialog onClose={() => setConfigOpen(false)} />}
    </div>
  );
}
