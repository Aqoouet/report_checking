// Ikar UI Kit — main App shell
// Mirrors frontend/src/App.tsx layout and behavior, with click-thru jobs.

const SAMPLE_JOBS = [
  {
    id: "j1", name: "Q4-final-report.docx", status: "processing",
    submittedAt: Date.now() - 1000 * 60 * 3,
    phase: "check · подраздел 12 / 24", current: 12, total: 24,
    log: "[14:32:01] orchestrator: starting pipeline\n[14:32:02] convert: docling-serve OK ✓\n[14:32:14] check: dispatching 24 chunks across 3 workers\n[14:32:48] check: 12/24 done",
    artifactDir: "U:\\reports\\Q4-final\\artifacts",
  },
  {
    id: "j2", name: "monthly-2026-03.docx", status: "done",
    submittedAt: Date.now() - 1000 * 60 * 18,
    artifactDir: "U:\\reports\\monthly-2026-03\\artifacts",
  },
  {
    id: "j3", name: "draft-spec.docx", status: "error",
    submittedAt: Date.now() - 1000 * 60 * 27,
    error: "Не удалось подключиться к LLM endpoint: timeout after 15s",
  },
  {
    id: "j4", name: "appendix-A.docx", status: "pending",
    submittedAt: Date.now() - 1000 * 30,
    queuePosition: 1,
  },
];

const App = () => {
  const { useState } = React;
  const [configOpen, setConfigOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const [jobs, setJobs] = useState(SAMPLE_JOBS);

  const handleCheck = () => {
    setStarting(true);
    setStartError("");
    setTimeout(() => {
      const newJob = {
        id: `j${Date.now()}`,
        name: `report-${new Date().toISOString().slice(0, 10)}.docx`,
        status: "processing",
        submittedAt: Date.now(),
        phase: "convert · ожидание docling",
        current: 0, total: 12,
      };
      setJobs(j => [newJob, ...j]);
      setStarting(false);
    }, 700);
  };

  const handleCancel = (id) => {
    setJobs(j => j.map(x => x.id === id ? { ...x, status: "cancelled" } : x));
  };

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <Logo size={32} />
        <span style={{ fontSize: "0.8rem", color: "var(--fg-3)", fontWeight: 600,
          textTransform: "uppercase", letterSpacing: "0.05em" }}>Ikar</span>
      </div>

      <Card wide>
        <h1 className="title">Проверка отчёта</h1>

        <div className="action-row">
          <Button variant="secondary" onClick={() => setConfigOpen(true)}>Настройки</Button>
          <Button variant="primary" onClick={handleCheck} disabled={starting}>
            {starting ? "Запускаем…" : "Проверить"}
          </Button>
        </div>

        {startError && <div className="start-error">{startError}</div>}

        <div className="jobs-section">
          <div className="jobs-section-title">Задачи</div>
          <div className="job-list">
            {jobs.length === 0
              ? <div className="jobs-empty">Задач пока нет</div>
              : jobs.map(job => <JobRow key={job.id} job={job} onCancel={handleCancel} />)
            }
          </div>
        </div>
      </Card>

      {configOpen && <ConfigDialog onClose={() => setConfigOpen(false)} />}
    </div>
  );
};

window.App = App;
