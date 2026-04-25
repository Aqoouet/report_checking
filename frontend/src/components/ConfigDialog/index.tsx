import { PARAM_DOCS } from "./paramDocs";
import { useConfigDialog } from "./useConfigDialog";

interface Props {
  onClose: () => void;
}

export default function ConfigDialog({ onClose }: Props) {
  const {
    yaml,
    setYaml,
    loading,
    saving,
    saveError,
    parseErrors,
    setParseErrors,
    activeDoc,
    setActiveDoc,
    fileInputRef,
    handleBackdrop,
    handleLoadFile,
    handleDownloadYaml,
    handleFileChange,
    handleSave,
  } = useConfigDialog(onClose);

  const activeParam = PARAM_DOCS.find((p) => p.key === activeDoc);

  return (
    <div className="modal-backdrop" onClick={handleBackdrop}>
      <div className="modal-box modal-box--wide" role="dialog" aria-modal="true" aria-label="Настройки">

        <div className="modal-header">
          <div className="modal-header-left">
            <h2 className="modal-title">Настройки конфигурации</h2>
            <span className="modal-subtitle">Редактируйте YAML напрямую</span>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        {loading ? (
          <div className="modal-loading">
            <div className="modal-loading-spinner" />
            Загрузка конфигурации…
          </div>
        ) : (
          <div className="cfg-layout">
            <div className="cfg-editor-col">
              <div className="cfg-editor-toolbar">
                <span className="cfg-editor-label">config.yaml</span>
                <button type="button" className="btn btn--sm btn--outline" onClick={handleLoadFile}>
                  <span>📂</span> Загрузить файл
                </button>
                <button type="button" className="btn btn--sm btn--outline" onClick={handleDownloadYaml}>
                  <span>💾</span> Сохранить файл
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".yaml,.yml,.txt"
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </div>

              <textarea
                className="cfg-yaml-editor"
                value={yaml}
                onChange={(e) => { setYaml(e.target.value); setParseErrors([]); }}
                spellCheck={false}
                autoCorrect="off"
                autoCapitalize="off"
              />

              {parseErrors.length > 0 && (
                <div className="cfg-parse-error">
                  <span className="cfg-error-icon">⚠</span>
                  <div className="cfg-parse-error-content">
                    <div>Проверьте значения в YAML:</div>
                    <ul className="cfg-field-errors">
                      {parseErrors.map((error, index) => (
                        <li key={`${error.field}-${index}`}>
                          <span className="cfg-field-error-name">{error.field}</span>: {error.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
              {saveError && (
                <div className="cfg-save-error">
                  <span className="cfg-error-icon">✕</span> {saveError}
                </div>
              )}
            </div>

            <div className="cfg-docs-col">
              <div className="cfg-docs-title">Параметры</div>
              <div className="cfg-params-list">
                {PARAM_DOCS.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    className={`cfg-param-item ${activeDoc === p.key ? "cfg-param-item--active" : ""}`}
                    onClick={() => setActiveDoc(activeDoc === p.key ? null : p.key)}
                  >
                    <span className="cfg-param-key">{p.key}</span>
                    <span className="cfg-param-type">{p.type}</span>
                  </button>
                ))}
              </div>

              {activeParam && (
                <div className="cfg-param-detail">
                  <div className="cfg-param-detail-title">{activeParam.title}</div>
                  <div className="cfg-param-detail-type">{activeParam.type}</div>
                  <p className="cfg-param-detail-desc">{activeParam.desc}</p>
                  <div className="cfg-param-detail-example-label">Пример:</div>
                  <pre className="cfg-param-detail-example">{activeParam.example}</pre>
                </div>
              )}

              {!activeParam && (
                <div className="cfg-docs-hint">
                  Нажмите на параметр выше, чтобы увидеть описание и пример.
                </div>
              )}
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Отмена
          </button>
          <button type="button" className="btn btn--primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}
