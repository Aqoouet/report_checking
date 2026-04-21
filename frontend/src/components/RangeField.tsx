import type { ValidateRangeResponse } from "../api";

export type RangeState = "empty" | "validating" | "valid" | "invalid";

interface Props {
  rangeInput: string;
  rangeState: RangeState;
  rangeResult: ValidateRangeResponse | null;
  rangeError: string;
  isValidating: boolean;
  canValidate: boolean;
  onChange: (value: string) => void;
  onValidate: () => void;
}

export default function RangeField({
  rangeInput,
  rangeState,
  rangeResult,
  rangeError,
  isValidating,
  canValidate,
  onChange,
  onValidate,
}: Props) {
  return (
    <div
      className="field field--hint-on-hover"
      data-hint="Укажите разделы для проверки: 3.1 или 3.2–3.5. Оставьте поле пустым, чтобы проверить весь документ."
    >
      <label className="label" htmlFor="range">
        Диапазон проверки
      </label>
      <div className="range-input-wrap">
        <div className="range-field-inner">
          <input
            id="range"
            className={[
              "input",
              rangeState === "valid" ? "input--valid" : "",
              rangeState === "invalid" ? "input--invalid" : "",
            ]
              .join(" ")
              .trim()}
            type="text"
            placeholder="раздел 3.2 или 3.3–3.5"
            value={rangeInput}
            onChange={(e) => onChange(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {isValidating && (
            <span className="range-spinner" title="Валидация…">⟳</span>
          )}
          {!isValidating && rangeState === "empty" && rangeInput !== "" && (
            <button
              type="button"
              className="range-clear-btn"
              onClick={() => onChange("")}
              title="Очистить поле"
              aria-label="Очистить поле диапазона"
            >
              ×
            </button>
          )}
          {!isValidating && rangeState === "valid" && (
            <span className="range-badge range-badge--ok">✓</span>
          )}
          {!isValidating && rangeState === "invalid" && (
            <span className="range-badge range-badge--err">✕</span>
          )}
        </div>
        <button
          type="button"
          className="btn btn--validate"
          onClick={onValidate}
          disabled={!canValidate}
          title="Проверить корректность введённого диапазона"
        >
          {isValidating ? "…" : "Валидировать"}
        </button>
      </div>

      {rangeState === "valid" && rangeResult?.display && (
        <span className="range-display">
          Будут проверяться{" "}
          {rangeResult.display.replace(/^[А-ЯЁ]/, (c) => c.toLowerCase())}
        </span>
      )}
      {rangeState === "invalid" && rangeError && (
        <span className="range-error">{rangeError}</span>
      )}
    </div>
  );
}
