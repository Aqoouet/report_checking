import { useEffect, useRef, useState } from "react";
import { getConfig, postConfig, type PipelineConfigData } from "../api";

interface Props {
  onClose: () => void;
}

const EMPTY: PipelineConfigData = {
  input_docx_path: "",
  output_dir: "",
  check_prompt: "",
  validation_prompt: "",
  summary_prompt: "",
  subchapters_range: "",
  chunk_size_tokens: 10000,
  temperature: null,
};

export default function ConfigDialog({ onClose }: Props) {
  const [form, setForm] = useState<PipelineConfigData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        if (cfg) setForm(cfg);
      })
      .catch(() => {/* use EMPTY */})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const set = <K extends keyof PipelineConfigData>(key: K, value: PipelineConfigData[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await postConfig(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="modal-backdrop" onClick={handleBackdrop}>
      <div className="modal-box" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Настройки">
        <div className="modal-header">
          <h2 className="modal-title">Настройки</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        {loading ? (
          <div className="modal-loading">Загрузка…</div>
        ) : (
          <form onSubmit={handleSave} className="config-form">
            <div className="config-section">
              <div className="config-section-title">Файлы</div>

              <div className="field">
                <label className="label" htmlFor="cfg-input-path">Путь к .docx</label>
                <input
                  id="cfg-input-path"
                  className="input"
                  type="text"
                  value={form.input_docx_path}
                  onChange={(e) => set("input_docx_path", e.target.value)}
                  placeholder="U:\path\to\report.docx"
                  required
                />
              </div>

              <div className="field">
                <label className="label" htmlFor="cfg-output-dir">Папка для результатов</label>
                <input
                  id="cfg-output-dir"
                  className="input"
                  type="text"
                  value={form.output_dir}
                  onChange={(e) => set("output_dir", e.target.value)}
                  placeholder="U:\path\to\output"
                  required
                />
              </div>
            </div>

            <div className="config-section">
              <div className="config-section-title">Диапазон подразделов</div>
              <div className="field">
                <input
                  className="input"
                  type="text"
                  value={form.subchapters_range}
                  onChange={(e) => set("subchapters_range", e.target.value)}
                  placeholder="напр. 1-3, 5 или пусто = все"
                />
              </div>
            </div>

            <div className="config-section">
              <div className="config-section-title">Параметры модели</div>
              <div className="config-row-2">
                <div className="field">
                  <label className="label" htmlFor="cfg-chunk">Размер чанка (токены)</label>
                  <input
                    id="cfg-chunk"
                    className="input"
                    type="number"
                    min={1000}
                    max={200000}
                    step={1000}
                    value={form.chunk_size_tokens}
                    onChange={(e) => set("chunk_size_tokens", Number(e.target.value))}
                  />
                </div>
                <div className="field">
                  <label className="label" htmlFor="cfg-temp">Temperature</label>
                  <input
                    id="cfg-temp"
                    className="input"
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={form.temperature ?? ""}
                    onChange={(e) => set("temperature", e.target.value === "" ? null : Number(e.target.value))}
                    placeholder="авто"
                  />
                </div>
              </div>
            </div>

            <div className="config-section">
              <div className="config-section-title">Промпты</div>

              <div className="field">
                <label className="label" htmlFor="cfg-check-prompt">Промпт проверки</label>
                <textarea
                  id="cfg-check-prompt"
                  className="prompt-textarea"
                  value={form.check_prompt}
                  onChange={(e) => set("check_prompt", e.target.value)}
                  rows={8}
                  spellCheck={false}
                />
              </div>

              <div className="field">
                <label className="label" htmlFor="cfg-val-prompt">
                  Промпт валидации{" "}
                  <span className="cfg-optional">(необязательно — пусто = пропустить этап)</span>
                </label>
                <textarea
                  id="cfg-val-prompt"
                  className="prompt-textarea"
                  value={form.validation_prompt}
                  onChange={(e) => set("validation_prompt", e.target.value)}
                  rows={5}
                  spellCheck={false}
                />
              </div>

              <div className="field">
                <label className="label" htmlFor="cfg-sum-prompt">
                  Промпт суммаризации{" "}
                  <span className="cfg-optional">(необязательно — пусто = пропустить этап)</span>
                </label>
                <textarea
                  id="cfg-sum-prompt"
                  className="prompt-textarea"
                  value={form.summary_prompt}
                  onChange={(e) => set("summary_prompt", e.target.value)}
                  rows={5}
                  spellCheck={false}
                />
              </div>
            </div>

            {error && <div className="cfg-error">{error}</div>}

            <div className="modal-actions">
              <button type="button" className="btn btn--secondary" onClick={onClose}>
                Отмена
              </button>
              <button type="submit" className="btn btn--primary" disabled={saving}>
                {saving ? "Сохраняем…" : "Сохранить"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
