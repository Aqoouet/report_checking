import type { ValidateRangeResponse } from "../api";

export type RangeState = "empty" | "validating" | "valid" | "invalid";

interface Props {
  filePath: string;
  rangeInput: string;
  rangeState: RangeState;
  rangeResult: ValidateRangeResponse | null;
  rangeError: string;
  isValidating: boolean;
  canValidate: boolean;
  onChange: (value: string) => void;
  onValidate: () => void;
}

function detectFileType(path: string): "docx" | "pdf" | "" {
  const lower = path.toLowerCase().trim();
  if (lower.endsWith(".docx")) return "docx";
  if (lower.endsWith(".pdf")) return "pdf";
  return "";
}

function detectInputType(text: string): "sections" | "pages" | "" {
  const lower = text.toLowerCase();
  if (/страниц|стр\./.test(lower)) return "pages";
  if (/раздел/.test(lower)) return "sections";
  return "";
}

export default function RangeField({
  filePath,
  rangeInput,
  rangeState,
  rangeResult,
  rangeError,
  isValidating,
  canValidate,
  onChange,
  onValidate,
}: Props) {
  const fileType = detectFileType(filePath);
  const inputType = detectInputType(rangeInput);
  const rangeTypeMismatch =
    rangeInput.trim() !== "" &&
    inputType !== "" &&
    fileType !== "" &&
    ((inputType === "sections" && fileType === "pdf") ||
      (inputType === "pages" && fileType === "docx"));

  return (
    <div className="field">
      <label className="label" htmlFor="range">
        Диапазон проверки{" "}
        <span className="label-optional">(необязательно)</span>
      </label>
      <div className="range-input-wrap">
        <div className="range-field-inner">
          <input
            id="range"
            className={`input${rangeState === "valid" ? " input--valid" : ""}${rangeState === "invalid" ? " input--invalid" : ""}`}
            type="text"
            placeholder={
              fileType === "pdf"
                ? "страница 1–3, 7"
                : "раздел 3.2 или 3.3–3.5"
            }
            value={rangeInput}
            onChange={(e) => onChange(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {isValidating && (
            <span className="range-spinner" title="Валидация…">⟳</span>
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
          {rangeResult.display.replace(/^[А-ЯЁ]/, (c: string) => c.toLowerCase())}
        </span>
      )}
      {rangeState === "invalid" && rangeError && (
        <span className="range-error">{rangeError}</span>
      )}

      {rangeTypeMismatch && (
        <div className="warning">
          {inputType === "sections" && fileType === "pdf"
            ? "Для PDF-файлов рекомендуется указывать страницы, а не разделы."
            : "Для DOCX-файлов рекомендуется указывать разделы, а не страницы."}
        </div>
      )}

      <span className="hint">
        Для .docx — разделы (раздел 3.1 или 3.2–3.5); для .pdf — страницы (страница 1–3, 7).
        Оставьте пустым для проверки всего документа.
      </span>
    </div>
  );
}
