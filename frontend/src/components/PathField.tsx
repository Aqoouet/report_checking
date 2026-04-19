export type PathFieldState = "empty" | "valid" | "invalid";

interface Props {
  filePath: string;
  pathState: PathFieldState;
  pathMessage: string;
  isValidating: boolean;
  canValidate: boolean;
  onChange: (value: string) => void;
  onValidate: () => void;
}

export default function PathField({
  filePath,
  pathState,
  pathMessage,
  isValidating,
  canValidate,
  onChange,
  onValidate,
}: Props) {
  return (
    <div
      className="field field--hint-on-hover"
      data-hint="Укажите путь к файлу в проектной папке на диске P: или в /filer/wps/wp. Принимаются только файлы .docx."
    >
      <label className="label" htmlFor="filepath">
        Путь к файлу
      </label>
      <div className="range-input-wrap">
        <div className="range-field-inner">
          <input
            id="filepath"
            className={[
              "input",
              pathState === "valid" ? "input--valid" : "",
              pathState === "invalid" ? "input--invalid" : "",
            ]
              .join(" ")
              .trim()}
            type="text"
            placeholder="P:\…\отчёт.docx или /filer/wps/wp/…/отчёт.docx"
            value={filePath}
            onChange={(e) => onChange(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {isValidating && (
            <span className="range-spinner" title="Проверка пути…">⟳</span>
          )}
          {!isValidating && pathState === "valid" && (
            <span className="range-badge range-badge--ok">✓</span>
          )}
          {!isValidating && pathState === "invalid" && (
            <span className="range-badge range-badge--err">✕</span>
          )}
        </div>
        <button
          type="button"
          className="btn btn--validate"
          onClick={onValidate}
          disabled={!canValidate}
          title="Проверить, доступен ли файл по этому пути на сервере"
        >
          {isValidating ? "…" : "Валидировать"}
        </button>
      </div>
      {pathState === "invalid" && pathMessage && (
        <span className="range-error">{pathMessage}</span>
      )}
      {pathState === "valid" && pathMessage && (
        <span className="path-ok-hint">{pathMessage}</span>
      )}
    </div>
  );
}
