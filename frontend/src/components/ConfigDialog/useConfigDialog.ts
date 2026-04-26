import { load, dump } from "js-yaml";
import { useEffect, useRef, useState, type Dispatch, type MouseEvent, type SetStateAction } from "react";
import {
  fetchConfigDefaults,
  fetchDefaultPrompts,
  fetchFieldHelp,
  fetchRuntimeInfo,
  getConfig,
  postConfig,
  validateInputPath,
  validateOutputDirPath,
  validateSubchaptersRange,
  type PipelineConfigData,
  type RuntimeInfo,
} from "../../api";
import { ApiError } from "../../api/client";

export type ConfigField = keyof PipelineConfigData;

export interface FormValues {
  input_docx_path: string;
  output_dir: string;
  subchapters_range: string;
  chunk_size_tokens: string;
  temperature: string;
  check_prompt: string;
  validation_prompt: string;
  summary_prompt: string;
}

export interface FieldValidationState {
  status: "idle" | "pending" | "success" | "error";
  message: string;
}

type HelpOpenState = Record<ConfigField, boolean>;
type HelpTextState = Record<ConfigField, string>;
type HelpLoadingState = Record<ConfigField, boolean>;
type ValidationStateMap = Record<ConfigField, FieldValidationState>;

const ALL_FIELDS: ConfigField[] = [
  "input_docx_path",
  "output_dir",
  "subchapters_range",
  "chunk_size_tokens",
  "temperature",
  "check_prompt",
  "validation_prompt",
  "summary_prompt",
];

const INITIAL_VALUES: FormValues = {
  input_docx_path: "",
  output_dir: "",
  subchapters_range: "",
  chunk_size_tokens: "",
  temperature: "",
  check_prompt: "",
  validation_prompt: "",
  summary_prompt: "",
};

function createHelpOpenState(): HelpOpenState {
  return {
    input_docx_path: false,
    output_dir: false,
    subchapters_range: false,
    chunk_size_tokens: false,
    temperature: false,
    check_prompt: false,
    validation_prompt: false,
    summary_prompt: false,
  };
}

function createHelpTextState(): HelpTextState {
  return {
    input_docx_path: "",
    output_dir: "",
    subchapters_range: "",
    chunk_size_tokens: "",
    temperature: "",
    check_prompt: "",
    validation_prompt: "",
    summary_prompt: "",
  };
}

function createHelpLoadingState(): HelpLoadingState {
  return {
    input_docx_path: false,
    output_dir: false,
    subchapters_range: false,
    chunk_size_tokens: false,
    temperature: false,
    check_prompt: false,
    validation_prompt: false,
    summary_prompt: false,
  };
}

function createValidationState(): ValidationStateMap {
  return {
    input_docx_path: { status: "idle", message: "" },
    output_dir: { status: "idle", message: "" },
    subchapters_range: { status: "idle", message: "" },
    chunk_size_tokens: { status: "idle", message: "" },
    temperature: { status: "idle", message: "" },
    check_prompt: { status: "idle", message: "" },
    validation_prompt: { status: "idle", message: "" },
    summary_prompt: { status: "idle", message: "" },
  };
}

function toFormValues(config: PipelineConfigData): FormValues {
  return {
    input_docx_path: config.input_docx_path,
    output_dir: config.output_dir,
    subchapters_range: config.subchapters_range,
    chunk_size_tokens: String(config.chunk_size_tokens),
    temperature: config.temperature == null ? "" : String(config.temperature),
    check_prompt: config.check_prompt,
    validation_prompt: config.validation_prompt,
    summary_prompt: config.summary_prompt,
  };
}

function applyFieldErrors(
  setValidation: Dispatch<SetStateAction<ValidationStateMap>>,
  fieldErrors: Partial<Record<ConfigField, string>>,
): void {
  setValidation((prev) => {
    const next = { ...prev };
    for (const field of ALL_FIELDS) {
      const message = fieldErrors[field];
      if (message) {
        next[field] = { status: "error", message };
      }
    }
    return next;
  });
}

function parseBackendFieldErrors(message: string): Partial<Record<ConfigField, string>> {
  const fieldErrors: Partial<Record<ConfigField, string>> = {};
  for (const part of message.split(";")) {
    const trimmed = part.trim();
    const sep = trimmed.indexOf(":");
    if (sep <= 0) continue;
    const field = trimmed.slice(0, sep).trim() as ConfigField;
    const text = trimmed.slice(sep + 1).trim();
    if (ALL_FIELDS.includes(field)) {
      fieldErrors[field] = text;
    }
  }
  return fieldErrors;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string {
  if (value == null) return "";
  return String(value);
}

function toYamlBackedFormValues(parsed: unknown, base: FormValues): FormValues {
  if (!isRecord(parsed)) {
    throw new Error("Файл конфигурации должен содержать YAML-объект с полями.");
  }

  return {
    input_docx_path: "input_docx_path" in parsed ? asString(parsed.input_docx_path) : base.input_docx_path,
    output_dir: "output_dir" in parsed ? asString(parsed.output_dir) : base.output_dir,
    subchapters_range: "subchapters_range" in parsed ? asString(parsed.subchapters_range) : base.subchapters_range,
    chunk_size_tokens: "chunk_size_tokens" in parsed ? asString(parsed.chunk_size_tokens) : base.chunk_size_tokens,
    temperature: "temperature" in parsed ? asString(parsed.temperature) : base.temperature,
    check_prompt: "check_prompt" in parsed ? asString(parsed.check_prompt) : base.check_prompt,
    validation_prompt: "validation_prompt" in parsed ? asString(parsed.validation_prompt) : base.validation_prompt,
    summary_prompt: "summary_prompt" in parsed ? asString(parsed.summary_prompt) : base.summary_prompt,
  };
}

export function useConfigDialog(onClose: () => void) {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeInfo | null>(null);
  const [helpOpen, setHelpOpen] = useState<HelpOpenState>(createHelpOpenState);
  const [helpText, setHelpText] = useState<HelpTextState>(createHelpTextState);
  const [helpLoading, setHelpLoading] = useState<HelpLoadingState>(createHelpLoadingState);
  const [validation, setValidation] = useState<ValidationStateMap>(createValidationState);
  const configFileInputRef = useRef<HTMLInputElement>(null);
  const [loadedOriginalYaml, setLoadedOriginalYaml] = useState("");

  useEffect(() => {
    Promise.all([
      getConfig().catch(() => null),
      fetchConfigDefaults(),
      fetchDefaultPrompts(),
      fetchRuntimeInfo().catch(() => null),
    ])
      .then(([config, defaults, prompts, info]) => {
        if (info) setRuntimeInfo(info);
        if (config) {
          setValues(toFormValues(config));
          return;
        }
        setValues(
          toFormValues({
            ...defaults,
            ...prompts,
          }),
        );
      })
      .catch(() => {
        setValues(INITIAL_VALUES);
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

  const handleBackdrop = (e: MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const setFieldValue = (field: ConfigField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setValidation((prev) => ({ ...prev, [field]: { status: "idle", message: "" } }));
    setSaveError("");
    setLoadedOriginalYaml("");
  };

  const toggleHelp = async (field: ConfigField) => {
    if (helpOpen[field]) {
      setHelpOpen((prev) => ({ ...prev, [field]: false }));
      return;
    }
    setHelpOpen((prev) => ({ ...prev, [field]: true }));
    if (helpText[field] || helpLoading[field]) {
      return;
    }
    setHelpLoading((prev) => ({ ...prev, [field]: true }));
    try {
      const text = await fetchFieldHelp(field);
      setHelpText((prev) => ({ ...prev, [field]: text }));
    } catch (err) {
      setHelpText((prev) => ({
        ...prev,
        [field]: err instanceof Error ? err.message : "Не удалось загрузить справку.",
      }));
    } finally {
      setHelpLoading((prev) => ({ ...prev, [field]: false }));
    }
  };

  const validateField = async (field: ConfigField) => {
    setSaveError("");
    setValidation((prev) => ({ ...prev, [field]: { status: "pending", message: "Проверяем…" } }));

    if (field === "input_docx_path") {
      try {
        const result = await validateInputPath(values.input_docx_path.trim());
        if (result.valid) {
          setValues((prev) => ({ ...prev, input_docx_path: result.mapped_path || prev.input_docx_path }));
          setValidation((prev) => ({
            ...prev,
            input_docx_path: { status: "success", message: result.message },
          }));
        } else {
          setValidation((prev) => ({
            ...prev,
            input_docx_path: { status: "error", message: result.message },
          }));
        }
      } catch (err) {
        setValidation((prev) => ({
          ...prev,
          input_docx_path: { status: "error", message: err instanceof Error ? err.message : "Ошибка проверки пути." },
        }));
      }
      return;
    }

    if (field === "output_dir") {
      try {
        const result = await validateOutputDirPath(values.output_dir.trim());
        if (result.valid) {
          setValues((prev) => ({ ...prev, output_dir: result.resolved_path || prev.output_dir }));
          setValidation((prev) => ({
            ...prev,
            output_dir: { status: "success", message: result.message },
          }));
        } else {
          setValidation((prev) => ({
            ...prev,
            output_dir: { status: "error", message: result.message },
          }));
        }
      } catch (err) {
        setValidation((prev) => ({
          ...prev,
          output_dir: { status: "error", message: err instanceof Error ? err.message : "Ошибка проверки папки." },
        }));
      }
      return;
    }

    if (field === "subchapters_range") {
      try {
        const result = await validateSubchaptersRange(values.subchapters_range.trim());
        if (result.valid) {
          if (result.display) {
            setValues((prev) => ({ ...prev, subchapters_range: result.display ?? prev.subchapters_range }));
          }
          setValidation((prev) => ({
            ...prev,
            subchapters_range: {
              status: "success",
              message: result.display || "Диапазон корректен.",
            },
          }));
        } else {
          setValidation((prev) => ({
            ...prev,
            subchapters_range: {
              status: "error",
              message: result.range_message || result.suggestion || "Диапазон не распознан.",
            },
          }));
        }
      } catch (err) {
        setValidation((prev) => ({
          ...prev,
          subchapters_range: { status: "error", message: err instanceof Error ? err.message : "Ошибка проверки диапазона." },
        }));
      }
      return;
    }

    if (field === "chunk_size_tokens") {
      const raw = values.chunk_size_tokens.trim();
      const maxChunk = runtimeInfo?.max_chunk_tokens ?? 3000;
      if (!raw) {
        setValidation((prev) => ({
          ...prev,
          chunk_size_tokens: { status: "error", message: "Укажите положительное целое число." },
        }));
        return;
      }
      const parsed = Number(raw);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        setValidation((prev) => ({
          ...prev,
          chunk_size_tokens: { status: "error", message: "Нужно положительное целое число." },
        }));
        return;
      }
      if (parsed > maxChunk) {
        setValidation((prev) => ({
          ...prev,
          chunk_size_tokens: {
            status: "error",
            message: `Максимум ${maxChunk.toLocaleString()}.`,
          },
        }));
        return;
      }
      setValidation((prev) => ({
        ...prev,
        chunk_size_tokens: { status: "success", message: `Значение в допустимом диапазоне 1-${maxChunk.toLocaleString()}.` },
      }));
      return;
    }

    if (field === "temperature") {
      const raw = values.temperature.trim();
      if (!raw) {
        setValidation((prev) => ({
          ...prev,
          temperature: { status: "success", message: "Будет использовано значение модели по умолчанию." },
        }));
        return;
      }
      const parsed = Number(raw);
      if (!Number.isFinite(parsed) || parsed < 0 || parsed > 2) {
        setValidation((prev) => ({
          ...prev,
          temperature: { status: "error", message: "Введите число от 0.0 до 2.0 или оставьте поле пустым." },
        }));
        return;
      }
      setValidation((prev) => ({
        ...prev,
        temperature: { status: "success", message: "Значение температуры корректно." },
      }));
    }
  };

  const handleLoadConfig = () => {
    configFileInputRef.current?.click();
  };

  const handleConfigFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const raw = await file.text();
      const parsed = load(raw);
      setValues((prev) => toYamlBackedFormValues(parsed, prev));
      setValidation(createValidationState());
      setSaveError("");
      setLoadedOriginalYaml(raw);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Не удалось прочитать YAML-конфигурацию.");
    } finally {
      e.target.value = "";
    }
  };

  const handleSaveConfig = () => {
    const payload = {
      input_docx_path: values.input_docx_path,
      output_dir: values.output_dir,
      subchapters_range: values.subchapters_range,
      chunk_size_tokens: values.chunk_size_tokens.trim(),
      temperature: values.temperature.trim() ? values.temperature.trim() : null,
      check_prompt: values.check_prompt,
      validation_prompt: values.validation_prompt,
      summary_prompt: values.summary_prompt,
    };
    const yamlText = dump(payload, {
      lineWidth: -1,
      noRefs: true,
      sortKeys: false,
    });
    const blob = new Blob([yamlText], { type: "application/x-yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "config.yaml";
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleApply = async () => {
    setSaveError("");
    const fieldErrors: Partial<Record<ConfigField, string>> = {};
    const inputDocxPath = values.input_docx_path.trim();
    const outputDir = values.output_dir.trim();
    const checkPrompt = values.check_prompt.trim();
    const chunkSize = Number(values.chunk_size_tokens.trim());
    const maxChunk = runtimeInfo?.max_chunk_tokens ?? 3000;

    if (!inputDocxPath) fieldErrors.input_docx_path = "Укажите путь к исходному .docx файлу.";
    if (!outputDir) fieldErrors.output_dir = "Папка результатов должна быть задана.";
    if (!checkPrompt) fieldErrors.check_prompt = "Основной промпт обязателен.";
    if (!values.chunk_size_tokens.trim()) {
      fieldErrors.chunk_size_tokens = "Укажите положительное целое число.";
    } else if (!Number.isInteger(chunkSize) || chunkSize <= 0) {
      fieldErrors.chunk_size_tokens = "Нужно положительное целое число.";
    } else if (chunkSize > maxChunk) {
      fieldErrors.chunk_size_tokens = `Максимум ${maxChunk.toLocaleString()}.`;
    }

    let temperature: number | null = null;
    const rawTemperature = values.temperature.trim();
    if (rawTemperature) {
      const parsedTemperature = Number(rawTemperature);
      if (!Number.isFinite(parsedTemperature) || parsedTemperature < 0 || parsedTemperature > 2) {
        fieldErrors.temperature = "Введите число от 0.0 до 2.0 или оставьте поле пустым.";
      } else {
        temperature = parsedTemperature;
      }
    }

    if (Object.keys(fieldErrors).length > 0) {
      applyFieldErrors(setValidation, fieldErrors);
      return;
    }

    const payload: PipelineConfigData = {
      input_docx_path: inputDocxPath,
      output_dir: outputDir,
      subchapters_range: values.subchapters_range.trim(),
      chunk_size_tokens: chunkSize,
      temperature,
      check_prompt: values.check_prompt,
      validation_prompt: values.validation_prompt,
      summary_prompt: values.summary_prompt,
    };

    setSaving(true);
    try {
      await postConfig({
        ...payload,
        _original_yaml: loadedOriginalYaml || undefined,
      });
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.code === "ERR_CONFIG_VALIDATION_FAILED") {
        applyFieldErrors(setValidation, parseBackendFieldErrors(err.backendMessage));
      }
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return {
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
    handleBackdrop,
    setFieldValue,
    toggleHelp,
    validateField,
    handleLoadConfig,
    handleConfigFileChange,
    handleSaveConfig,
    handleApply,
  };
}
