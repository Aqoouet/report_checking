import { useEffect, useRef, useState } from "react";
import { fetchDefaultPrompts, fetchRuntimeInfo, getConfig, postConfig, type PipelineConfigData, type RuntimeInfo } from "../api";

interface Props {
  onClose: () => void;
}

interface ParamDoc {
  key: string;
  title: string;
  type: string;
  desc: string;
  example: string;
}

const PARAM_DOCS: ParamDoc[] = [
  {
    key: "input_docx_path",
    title: "input_docx_path",
    type: "string",
    desc: "Абсолютный путь к исходному файлу отчёта в формате .docx. Вставляйте путь как есть.\n\n⚠ Windows: в данный момент поддерживается только диск P:\\. Пути на других дисках (C:\\, D:\\ и др.) и сетевые пути (\\\\server\\...) не поддерживаются.\n\nLinux: любой абсолютный путь принимается без изменений.",
    example: "input_docx_path: P:\\WP13C\\report.docx",
  },
  {
    key: "output_dir",
    title: "output_dir",
    type: "string",
    desc: "Папка, куда будут сохранены результаты проверки. Создаётся автоматически, если не существует. Вставляйте путь как есть.\n\n⚠ Windows: в данный момент поддерживается только диск P:\\.\n\nПо умолчанию: Windows — P:\\temp\\report_check_results\\, Linux — /filer/wps/wp/temp/report_check_results",
    example: "output_dir: P:\\temp\\report_check_results\\",
  },
  {
    key: "subchapters_range",
    title: "subchapters_range",
    type: "string (необязательно)",
    desc: "Диапазон подразделов для проверки. Пустая строка = проверить все. Формат: «1-3, 5» означает разделы 1, 2, 3 и 5.",
    example: 'subchapters_range: "1-3, 5"',
  },
  {
    key: "chunk_size_tokens",
    title: "chunk_size_tokens",
    type: "integer",
    desc: "Максимальный размер одного чанка текста в токенах, передаваемого в модель. Увеличьте для длинных разделов, уменьшите при ошибках context length.\n\nВерхний предел задаётся переменной окружения MAX_CHUNK_TOKENS (по умолчанию 15 000).",
    example: "chunk_size_tokens: 3000",
  },
  {
    key: "temperature",
    title: "temperature",
    type: "float | null",
    desc: "Температура генерации модели (0.0–2.0). null = используется значение по умолчанию модели. Меньше = детерминированнее.",
    example: "temperature: null",
  },
  {
    key: "check_prompt",
    title: "check_prompt",
    type: "string (многострочный)",
    desc: "Основной промпт для проверки раздела. Используйте блочный скалярный синтаксис YAML (символ | после двоеточия). Переносы строк сохраняются.",
    example: "check_prompt: |\n  Вы — строгий рецензент.\n  Проверьте раздел по критериям...",
  },
  {
    key: "validation_prompt",
    title: "validation_prompt",
    type: "string (необязательно)",
    desc: "Промпт для этапа валидации результатов проверки. Пустая строка — этап пропускается.",
    example: 'validation_prompt: ""',
  },
  {
    key: "summary_prompt",
    title: "summary_prompt",
    type: "string (необязательно)",
    desc: "Промпт для финального суммирования. Пустая строка — этап пропускается.",
    example: 'summary_prompt: ""',
  },
];

function getDefaultScalars(isLinux: boolean): Pick<PipelineConfigData, "input_docx_path" | "output_dir" | "subchapters_range" | "chunk_size_tokens" | "temperature"> {
  return {
    input_docx_path: isLinux ? "/filer/wps/wp/" : "P:\\путь\\к\\файлу.docx",
    output_dir: isLinux ? "/filer/wps/wp/temp/report_check_results" : "P:\\temp\\report_check_results\\",
    subchapters_range: "",
    chunk_size_tokens: 3000,
    temperature: null,
  };
}

function serializeToYaml(cfg: PipelineConfigData): string {
  const lines: string[] = [];

  const pathFields: Array<[keyof PipelineConfigData, string]> = [
    ["input_docx_path", "Путь к исходному файлу отчёта (.docx) — вставьте как есть. Для Windows только P:\\..., для Linux любые пути"],
    ["output_dir", "Папка для сохранения результатов — вставьте как есть"],
  ];

  for (const [key, comment] of pathFields) {
    lines.push(`# ${comment}`);
    lines.push(`${key}: ${String(cfg[key] ?? "")}`);
    lines.push("");
  }

  const scalarFields: Array<[keyof PipelineConfigData, string]> = [
    ["subchapters_range", 'Диапазон подразделов (пусто = все, пример: "1-3, 5")'],
    ["chunk_size_tokens", "Размер чанка в токенах"],
    ["temperature", "Температура модели (null = по умолчанию)"],
  ];

  for (const [key, comment] of scalarFields) {
    lines.push(`# ${comment}`);
    const val = cfg[key];
    if (val === null || val === undefined) {
      lines.push(`${key}: null`);
    } else if (typeof val === "number") {
      lines.push(`${key}: ${val}`);
    } else {
      lines.push(`${key}: "${String(val).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`);
    }
    lines.push("");
  }

  const blockFields: Array<[keyof PipelineConfigData, string]> = [
    ["check_prompt", "Промпт проверки (используйте | для многострочного текста)"],
    ["validation_prompt", "Промпт валидации (пусто = пропустить этап)"],
    ["summary_prompt", "Промпт суммаризации (пусто = пропустить этап)"],
  ];

  for (const [key, comment] of blockFields) {
    lines.push(`# ${comment}`);
    const val = String(cfg[key] ?? "");
    if (!val || !val.includes("\n")) {
      lines.push(`${key}: "${val.replace(/"/g, '\\"')}"`);
    } else {
      lines.push(`${key}: |`);
      for (const line of val.split("\n")) {
        lines.push(`  ${line}`);
      }
    }
    lines.push("");
  }

  return lines.join("\n");
}

function parseYaml(text: string): PipelineConfigData {
  const result: Partial<PipelineConfigData> = {};
  const lines = text.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed || trimmed.startsWith("#")) {
      i++;
      continue;
    }

    const colonIdx = trimmed.indexOf(":");
    if (colonIdx < 0) { i++; continue; }

    const key = trimmed.slice(0, colonIdx).trim();
    const rest = trimmed.slice(colonIdx + 1).trim();

    if (rest === "|" || rest === "|-") {
      i++;
      const blockLines: string[] = [];
      const baseIndent = lines[i] ? lines[i].match(/^(\s*)/)?.[1].length ?? 0 : 0;
      while (i < lines.length) {
        const bline = lines[i];
        if (!bline.trim() && i + 1 < lines.length && (lines[i + 1].match(/^(\s*)/)?.[1].length ?? 0) < baseIndent) {
          break;
        }
        const indent = bline.match(/^(\s*)/)?.[1].length ?? 0;
        if (bline.trim() && indent < baseIndent) break;
        blockLines.push(bline.slice(baseIndent));
        i++;
      }
      let blockVal = blockLines.join("\n");
      if (rest === "|-") blockVal = blockVal.replace(/\n+$/, "");
      else blockVal = blockVal.replace(/\n+$/, "\n");
      (result as Record<string, unknown>)[key] = blockVal;
      continue;
    }

    let val: string | number | null;
    if (rest === "null" || rest === "~") {
      val = null;
    } else if (/^-?\d+(\.\d+)?$/.test(rest)) {
      val = Number(rest);
    } else if ((rest.startsWith('"') && rest.endsWith('"')) || (rest.startsWith("'") && rest.endsWith("'"))) {
      val = rest
        .slice(1, -1)
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, "\\");
    } else {
      val = rest;
    }
    (result as Record<string, unknown>)[key] = val;
    i++;
  }

  return {
    input_docx_path: String(result.input_docx_path ?? ""),
    output_dir: String(result.output_dir ?? ""),
    check_prompt: String(result.check_prompt ?? ""),
    validation_prompt: String(result.validation_prompt ?? ""),
    summary_prompt: String(result.summary_prompt ?? ""),
    subchapters_range: String(result.subchapters_range ?? ""),
    chunk_size_tokens: typeof result.chunk_size_tokens === "number" ? result.chunk_size_tokens : 3000,
    temperature: result.temperature === null || result.temperature === undefined
      ? null
      : typeof result.temperature === "number"
        ? result.temperature
        : null,
  };
}


export default function ConfigDialog({ onClose }: Props) {
  const [yaml, setYaml] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [parseError, setParseError] = useState("");
  const [activeDoc, setActiveDoc] = useState<string | null>(null);
  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeInfo | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([getConfig(), fetchDefaultPrompts(), fetchRuntimeInfo().catch(() => null)])
      .then(([cfg, defaults, info]) => {
        if (info) setRuntimeInfo(info);
        const isLinux = info?.os === "linux";
        if (cfg) {
          setYaml(serializeToYaml(cfg));
        } else {
          setYaml(serializeToYaml({ ...getDefaultScalars(isLinux), ...defaults }));
        }
      })
      .catch(() => {
        setYaml(serializeToYaml({ ...getDefaultScalars(false), check_prompt: "", validation_prompt: "", summary_prompt: "" }));
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleLoadFile = () => {
    fileInputRef.current?.click();
  };

  const handleDownloadYaml = () => {
    const blob = new Blob([yaml], { type: "text/yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "config.yaml";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setYaml(ev.target?.result as string);
      setParseError("");
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handleSave = async () => {
    setParseError("");
    setSaveError("");
    let cfg: PipelineConfigData;
    try {
      cfg = parseYaml(yaml);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Ошибка парсинга YAML");
      return;
    }
    const maxChunk = runtimeInfo?.max_chunk_tokens ?? 3000;
    if (cfg.chunk_size_tokens > maxChunk) {
      setParseError(`chunk_size_tokens: максимум ${maxChunk.toLocaleString()} (задан параметром MAX_CHUNK_TOKENS)`);
      return;
    }
    setSaving(true);
    try {
      await postConfig(cfg);
      onClose();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

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
                onChange={(e) => { setYaml(e.target.value); setParseError(""); }}
                spellCheck={false}
                autoCorrect="off"
                autoCapitalize="off"
              />

              {parseError && (
                <div className="cfg-parse-error">
                  <span className="cfg-error-icon">⚠</span> {parseError}
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
