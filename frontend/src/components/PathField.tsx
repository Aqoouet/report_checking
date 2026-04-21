import { useState } from "react";

export type PathFieldState = "empty" | "valid" | "invalid";

const PATH_EXAMPLES: { windows: string; linux: string }[] = [
  { windows: "P:\\", linux: "/filer/wps/wp/" },
  { windows: "\\\\e0-filer03\\allcreatex\\createx\\", linux: "/filer/users/" },
];

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
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <div className="field">
      <div className="label-row">
        <label className="label" htmlFor="filepath">
          Путь к файлу
        </label>
        <button
          type="button"
          className="help-btn"
          onClick={() => setHelpOpen((v) => !v)}
          aria-label="Справка по формату пути"
          aria-expanded={helpOpen}
        >
          ?
        </button>
      </div>
      {helpOpen && (
        <div className="help-popup">
          <p className="help-popup__intro">Принимаются файлы <code>.docx</code>. Поддерживаемые префиксы путей:</p>
          <table className="help-popup__table">
            <tbody>
              {PATH_EXAMPLES.map(({ windows, linux }) => (
                <tr key={windows}>
                  <td><code>{windows}…\отчёт.docx</code></td>
                  <td className="help-popup__arrow">→</td>
                  <td><code>{linux}…/отчёт.docx</code></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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
          {!isValidating && pathState === "empty" && filePath !== "" && (
            <button
              type="button"
              className="range-clear-btn"
              onClick={() => onChange("")}
              title="Очистить поле"
              aria-label="Очистить поле пути"
            >
              ×
            </button>
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
