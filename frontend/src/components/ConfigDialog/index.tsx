import { useConfigDialog } from "./useConfigDialog";

interface Props {
  onClose: () => void;
}

export default function ConfigDialog({ onClose }: Props) {
  const {
    values,
    loading,
    saving,
    saveError,
    runtimeInfo,
    helpOpen,
    helpText,
    helpLoading,
    validation,
    configFileInputRef,
    setFieldValue,
    toggleHelp,
    validateField,
    handleLoadConfig,
    handleConfigFileChange,
    handleSaveConfig,
    handleApply,
  } = useConfigDialog(onClose);

  const validationFields = new Set<keyof typeof values>([
    "input_docx_path",
    "output_dir",
    "subchapters_range",
    "chunk_size_tokens",
    "temperature",
  ]);

  const fieldMeta: Array<{
    key: keyof typeof values;
    label: string;
    multiline?: boolean;
    readonly?: boolean;
  }> = [
    { key: "input_docx_path", label: "Путь к .docx файлу" },
    { key: "output_dir", label: "Папка результатов", readonly: true },
    { key: "subchapters_range", label: "Диапазон подразделов" },
    { key: "chunk_size_tokens", label: "Размер чанка, токены" },
    { key: "temperature", label: "Temperature" },
    { key: "check_prompt", label: "Промпт проверки", multiline: true },
    { key: "validation_prompt", label: "Промпт валидации", multiline: true },
    { key: "summary_prompt", label: "Промпт суммаризации", multiline: true },
  ];

  return (
    <div className="modal-backdrop">
      <div className="modal-box modal-box--wide" role="dialog" aria-modal="true" aria-label="Настройки">
        <div className="modal-header">
          <div className="modal-header-left">
            <h2 className="modal-title">Настройки конфигурации</h2>
            <span className="modal-subtitle">Редактируйте параметры по полям</span>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        {loading ? (
          <div className="modal-loading">
            <div className="modal-loading-spinner" />
            Загрузка конфигурации…
          </div>
        ) : (
          <div className="cfg-form">
            <input
              ref={configFileInputRef}
              type="file"
              accept=".yaml,.yml,text/yaml,application/x-yaml"
              style={{ display: "none" }}
              onChange={handleConfigFileChange}
            />

            {fieldMeta.map((field) => {
              const fieldValidation = validation[field.key];
              const hasValidationButton = validationFields.has(field.key);
              const validationClass =
                fieldValidation.status === "success"
                  ? "cfg-field-result cfg-field-result--success"
                  : fieldValidation.status === "error"
                    ? "cfg-field-result cfg-field-result--error"
                    : "cfg-field-result";

              return (
                <div key={field.key} className="cfg-form-field">
                  <div className="cfg-field-head">
                    <label className="cfg-field-label" htmlFor={`cfg-${field.key}`}>
                      <span>{field.label}</span>
                      <button
                        type="button"
                        className="cfg-icon-btn cfg-icon-btn--help"
                        aria-label={`Справка: ${field.label}`}
                        title="Показать справку"
                        onClick={() => { void toggleHelp(field.key); }}
                      >
                        ?
                      </button>
                    </label>
                  </div>

                  <div className="cfg-field-input-row">
                    {field.multiline ? (
                      <textarea
                        id={`cfg-${field.key}`}
                        className="cfg-textarea"
                        value={values[field.key]}
                        onChange={(e) => setFieldValue(field.key, e.target.value)}
                        spellCheck={false}
                      />
                    ) : (
                      <input
                        id={`cfg-${field.key}`}
                        className={`cfg-input ${field.readonly ? "cfg-input--readonly" : ""}`}
                        value={values[field.key]}
                        onChange={(e) => setFieldValue(field.key, e.target.value)}
                        readOnly={field.readonly}
                        disabled={field.readonly}
                        spellCheck={false}
                      />
                    )}

                    {hasValidationButton && (
                      <button
                        type="button"
                        className="cfg-icon-btn cfg-icon-btn--side"
                        aria-label={`Проверить поле ${field.label}`}
                        title="Проверить значение"
                        onClick={() => { void validateField(field.key); }}
                        disabled={fieldValidation.status === "pending"}
                      >
                        ✓
                      </button>
                    )}
                  </div>

                  {field.key === "chunk_size_tokens" && runtimeInfo && (
                    <div className="cfg-field-meta">
                      Runtime максимум: {runtimeInfo.max_chunk_tokens.toLocaleString()}
                    </div>
                  )}

                  {helpOpen[field.key] && (
                    <div className="cfg-inline-panel cfg-inline-panel--help">
                      {helpLoading[field.key] ? "Загрузка справки…" : helpText[field.key]}
                    </div>
                  )}

                  {fieldValidation.status !== "idle" && (
                    <div className={validationClass}>{fieldValidation.message}</div>
                  )}
                </div>
              );
            })}

            {saveError && (
              <div className="cfg-save-error">
                <span className="cfg-error-icon">✕</span> {saveError}
              </div>
            )}
          </div>
        )}
        <div className="modal-footer">
          <div className="modal-footer-group">
            <button type="button" className="btn btn--secondary" onClick={handleLoadConfig} disabled={saving || loading}>
              Загрузить конфигурацию
            </button>
            <button type="button" className="btn btn--secondary" onClick={handleSaveConfig} disabled={saving || loading}>
              Сохранить конфигурацию
            </button>
          </div>
          <div className="modal-footer-group">
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="button" className="btn btn--primary" onClick={handleApply} disabled={saving || loading}>
              {saving ? "Применяем…" : "Применить"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
