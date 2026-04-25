import * as jsYaml from "js-yaml";
import type { PipelineConfigData } from "../../api";

export function getDefaultScalars(isLinux: boolean): Pick<PipelineConfigData, "input_docx_path" | "output_dir" | "subchapters_range" | "chunk_size_tokens" | "temperature"> {
  return {
    input_docx_path: isLinux ? "/filer/wps/wp/.../отчет.docx" : "P:\\путь\\к\\файлу.docx",
    output_dir: isLinux ? "/filer/wps/wp/temp/report_check_results" : "P:\\temp\\report_check_results\\",
    subchapters_range: "",
    chunk_size_tokens: 3000,
    temperature: null,
  };
}

export function serializeToYaml(cfg: PipelineConfigData): string {
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

export function parseYaml(text: string): PipelineConfigData {
  const raw = jsYaml.load(text) as Record<string, unknown>;
  if (!raw || typeof raw !== "object") throw new Error("Неверный YAML");
  const str = (key: string) => {
    const v = raw[key];
    return v == null ? "" : String(v);
  };
  const temp = raw["temperature"];
  return {
    input_docx_path: str("input_docx_path"),
    output_dir: str("output_dir"),
    check_prompt: str("check_prompt"),
    validation_prompt: str("validation_prompt"),
    summary_prompt: str("summary_prompt"),
    subchapters_range: str("subchapters_range"),
    chunk_size_tokens: typeof raw["chunk_size_tokens"] === "number" ? raw["chunk_size_tokens"] : 3000,
    temperature: temp == null ? null : typeof temp === "number" ? temp : null,
  };
}
