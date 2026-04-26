// Ikar UI Kit — ConfigDialog (settings modal)
// Recreates the YAML-config editor with field validation.

const FIELD_META = [
  { key: "input_docx_path", label: "Путь к .docx файлу" },
  { key: "output_dir", label: "Папка результатов", readonly: true },
  { key: "subchapters_range", label: "Диапазон подразделов" },
  { key: "chunk_size_tokens", label: "Размер чанка, токены" },
  { key: "temperature", label: "Temperature" },
  { key: "check_prompt", label: "Промпт проверки", multiline: true },
];

const DEFAULT_VALUES = {
  input_docx_path: "U:\\reports\\Q4-final.docx",
  output_dir: "/output",
  subchapters_range: "1-12",
  chunk_size_tokens: "3000",
  temperature: "0.2",
  check_prompt: "Проверь раздел технического отчёта на корректность и непротиворечивость. Используй формальный стиль.",
};

const ConfigDialog = ({ onClose, onApply }) => {
  const { useState } = React;
  const [values, setValues] = useState(DEFAULT_VALUES);
  const [validation, setValidation] = useState({});
  const [helpOpen, setHelpOpen] = useState({});

  const setVal = (key, v) => setValues(s => ({ ...s, [key]: v }));

  const validate = (key) => {
    setValidation(s => ({ ...s, [key]: { status: "pending" } }));
    setTimeout(() => {
      setValidation(s => ({ ...s, [key]: { status: "success", message: "✓ Значение валидно" } }));
    }, 600);
  };

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box modal-box--wide" role="dialog">
        <div className="modal-header">
          <div className="modal-header-left">
            <h2 className="modal-title">Настройки конфигурации</h2>
            <span className="modal-subtitle">Редактируйте параметры по полям</span>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        <div className="cfg-form">
          {FIELD_META.map(field => {
            const v = validation[field.key] || { status: "idle" };
            const cls = v.status === "success" ? "cfg-field-result cfg-field-result--success"
                      : v.status === "error" ? "cfg-field-result cfg-field-result--error"
                      : "cfg-field-result";
            return (
              <div key={field.key} className="cfg-form-field">
                <div className="cfg-field-head">
                  <label className="cfg-field-label">
                    <span>{field.label}</span>
                    <button className="cfg-icon-btn cfg-icon-btn--help"
                      onClick={() => setHelpOpen(s => ({ ...s, [field.key]: !s[field.key] }))}>?</button>
                  </label>
                </div>
                <div className="cfg-field-input-row">
                  {field.multiline
                    ? <textarea className="cfg-textarea" value={values[field.key]}
                        onChange={e => setVal(field.key, e.target.value)} />
                    : <input className={`cfg-input${field.readonly ? " cfg-input--readonly" : ""}`}
                        value={values[field.key]} readOnly={field.readonly}
                        onChange={e => setVal(field.key, e.target.value)} />
                  }
                  {!field.multiline && !field.readonly && (
                    <button className="cfg-icon-btn cfg-icon-btn--side"
                      onClick={() => validate(field.key)} disabled={v.status === "pending"}>✓</button>
                  )}
                </div>
                {helpOpen[field.key] && (
                  <div className="cfg-inline-panel cfg-inline-panel--help">
                    Описание поля «{field.label}». Здесь обычно подсказки по формату значений и ограничениям.
                  </div>
                )}
                {v.status !== "idle" && v.message && (
                  <div className={cls}>{v.message}</div>
                )}
              </div>
            );
          })}
        </div>

        <div className="modal-footer">
          <div className="modal-footer-group">
            <Button variant="secondary">Загрузить конфигурацию</Button>
            <Button variant="secondary">Сохранить конфигурацию</Button>
          </div>
          <div className="modal-footer-group">
            <Button variant="secondary" onClick={onClose}>Отмена</Button>
            <Button variant="primary" onClick={() => { onApply && onApply(values); onClose(); }}>Применить</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

window.ConfigDialog = ConfigDialog;
