import * as jsYaml from "js-yaml";
import type { PipelineConfigData } from "../../api";

export type ConfigYamlField = keyof PipelineConfigData | "yaml";

export interface ConfigYamlFieldError {
  field: ConfigYamlField;
  message: string;
}

export class ConfigYamlValidationError extends Error {
  fieldErrors: ConfigYamlFieldError[];
  draftConfig?: PipelineConfigData;

  constructor(fieldErrors: ConfigYamlFieldError[], message = "Проверьте значения в YAML", draftConfig?: PipelineConfigData) {
    super(message);
    this.name = "ConfigYamlValidationError";
    this.fieldErrors = fieldErrors;
    this.draftConfig = draftConfig;
  }
}

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
  let loaded: unknown;
  try {
    loaded = jsYaml.load(text);
  } catch (error) {
    const details = error instanceof Error ? `: ${error.message}` : "";
    throw new ConfigYamlValidationError([{ field: "yaml", message: `Неверный YAML${details}` }], "Ошибка парсинга YAML");
  }

  if (!loaded || typeof loaded !== "object" || Array.isArray(loaded)) {
    throw new ConfigYamlValidationError([{ field: "yaml", message: "Корневой YAML должен быть объектом с параметрами конфигурации" }]);
  }

  const raw = loaded as Record<string, unknown>;
  const fieldErrors: ConfigYamlFieldError[] = [];

  const readString = (field: keyof PipelineConfigData): string => {
    const value = raw[field];
    if (value == null) return "";
    if (typeof value === "string") return value;
    fieldErrors.push({ field, message: "Ожидается строка; массивы, объекты и числа не преобразуются автоматически" });
    return "";
  };

  const readChunkSize = (): number => {
    const field: keyof PipelineConfigData = "chunk_size_tokens";
    const value = raw[field];
    if (value == null) {
      fieldErrors.push({ field, message: "Укажите положительное целое число" });
      return 0;
    }
    if (typeof value !== "number" || !Number.isFinite(value)) {
      fieldErrors.push({ field, message: "Ожидается число без кавычек" });
      return 0;
    }
    if (!Number.isInteger(value)) {
      fieldErrors.push({ field, message: "Ожидается целое число" });
      return value;
    }
    if (value <= 0) {
      fieldErrors.push({ field, message: "Значение должно быть больше 0" });
    }
    return value;
  };

  const readTemperature = (): number | null => {
    const field: keyof PipelineConfigData = "temperature";
    const value = raw[field];
    if (value == null || value === "") return null;
    if (typeof value !== "number" || !Number.isFinite(value)) {
      fieldErrors.push({ field, message: "Ожидается число от 0.0 до 2.0 или null" });
      return null;
    }
    if (value < 0 || value > 2) {
      fieldErrors.push({ field, message: "Значение должно быть в диапазоне 0.0..2.0" });
    }
    return value;
  };

  const config: PipelineConfigData = {
    input_docx_path: readString("input_docx_path"),
    output_dir: readString("output_dir"),
    check_prompt: readString("check_prompt"),
    validation_prompt: readString("validation_prompt"),
    summary_prompt: readString("summary_prompt"),
    subchapters_range: readString("subchapters_range"),
    chunk_size_tokens: readChunkSize(),
    temperature: readTemperature(),
  };

  if (fieldErrors.length > 0) {
    throw new ConfigYamlValidationError(fieldErrors, "Проверьте значения в YAML", config);
  }

  return config;
}
