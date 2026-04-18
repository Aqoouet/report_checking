import { useState } from "react";
import type { StatusResponse } from "../api";

interface Props {
  progress: StatusResponse | null;
  onStop: () => void;
}

export default function ProcessingView({ progress, onStop }: Props) {
  const [prevResultOpen, setPrevResultOpen] = useState(false);

  const pct =
    progress && progress.total_checkpoints > 0
      ? progress.checkpoint_sub_total
        ? Math.round(
            ((progress.current_checkpoint +
              (progress.checkpoint_sub_current ?? 0) /
                progress.checkpoint_sub_total) /
              progress.total_checkpoints) *
              100,
          )
        : Math.round(
            (progress.current_checkpoint / progress.total_checkpoints) * 100,
          )
      : 0;

  const prevResult = progress?.previous_result ?? "";
  const currentSubName = progress?.checkpoint_sub_name ?? "";

  return (
    <div className="status-block">
      {currentSubName ? (
        <div className="progress-sub-name">
          Сейчас проверяется раздел {currentSubName}
        </div>
      ) : (
        <div className="progress-label">Инициализация…</div>
      )}

      {progress && progress.total_checkpoints > 1 && (
        <div className="progress-label progress-label--sub">
          {`Критерий ${Math.min(progress.current_checkpoint + 1, progress.total_checkpoints)} из ${progress.total_checkpoints}${
            progress.checkpoint_sub_location
              ? ` · ${progress.checkpoint_sub_location}`
              : ""
          }`}
        </div>
      )}

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      {prevResult && (
        <div className="prev-result-block">
          <button
            className="prev-result-toggle"
            onClick={() => setPrevResultOpen((o) => !o)}
            type="button"
          >
            {prevResultOpen ? "▲" : "▼"} Результат проверки предыдущего раздела
          </button>
          {prevResultOpen && (
            <div className="prev-result-body">{prevResult}</div>
          )}
        </div>
      )}

      <div className="processing-actions">
        <p className="processing-note">
          Нейросеть выполняет проверки по очереди. Не закрывайте вкладку.
        </p>
        <button className="btn btn--danger" onClick={onStop} type="button">
          Остановить
        </button>
      </div>
    </div>
  );
}
