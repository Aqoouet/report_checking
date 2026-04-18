import { useState } from "react";
import type { StatusResponse } from "../api";

interface Props {
  progress: StatusResponse | null;
  onStop: () => void;
  isStopping?: boolean;
}

export default function ProcessingView({ progress, onStop, isStopping = false }: Props) {
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
          Сейчас проверяется раздел «{currentSubName}»
        </div>
      ) : (
        <div className="processing-phase-convert">
          <div className="progress-label">Конвертация в md формат…</div>
          <p className="processing-docling-note">
            Перед проверкой документ преобразуется в <strong>Markdown</strong> (сервис Docling),
            затем по разделам выполняется анализ нейросетью. На больших файлах конвертация может
            занять заметное время.
          </p>
        </div>
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
        {isStopping && (
          <div className="stop-pending" aria-live="polite">
            <span className="stop-pending__spinner" aria-hidden />
            <span>
              Останавливаем… Дождитесь ответа модели на текущий фрагмент — это может занять
              несколько секунд.
            </span>
          </div>
        )}
        <button
          className="btn btn--danger"
          onClick={onStop}
          type="button"
          disabled={isStopping}
        >
          {isStopping ? "Остановка…" : "Остановить"}
        </button>
      </div>
    </div>
  );
}
