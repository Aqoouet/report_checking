import { resultUrl } from "../api";

export type TerminalStage = "done" | "cancelled" | "error";

interface Props {
  stage: TerminalStage;
  jobId: string;
  errorMsg: string;
  totalCheckpoints: number;
  onReset: () => void;
}

export default function ResultView({
  stage,
  jobId,
  errorMsg,
  totalCheckpoints,
  onReset,
}: Props) {
  if (stage === "done") {
    return (
      <div className="status-block status-block--done">
        <div className="done-icon">✓</div>
        <p className="done-text">
          Проверено {totalCheckpoints} критери
          {totalCheckpoints === 1 ? "й" : "ев"}. Отчёт готов.
        </p>
        <a
          href={resultUrl(jobId)}
          download="report_errors.txt"
          className="btn btn--primary"
        >
          Скачать отчёт об ошибках
        </a>
        <button className="btn btn--secondary" onClick={onReset}>
          Проверить другой файл
        </button>
      </div>
    );
  }

  if (stage === "cancelled") {
    return (
      <div className="status-block status-block--cancelled">
        <div className="stopped-icon">⏹</div>
        <p className="done-text">Проверка остановлена. Частичный отчёт готов.</p>
        <a
          href={resultUrl(jobId)}
          download="report_errors_partial.txt"
          className="btn btn--primary"
        >
          Скачать частичный отчёт
        </a>
        <button className="btn btn--secondary" onClick={onReset}>
          Проверить снова
        </button>
      </div>
    );
  }

  return (
    <div className="status-block status-block--error">
      <div className="error-icon">✕</div>
      <p className="error-text">{errorMsg}</p>
      <button className="btn btn--secondary" onClick={onReset}>
        Попробовать снова
      </button>
    </div>
  );
}
