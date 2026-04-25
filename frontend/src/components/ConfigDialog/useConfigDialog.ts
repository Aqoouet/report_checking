import { useEffect, useRef, useState } from "react";
import { fetchDefaultPrompts, fetchRuntimeInfo, getConfig, postConfig, type PipelineConfigData, type RuntimeInfo } from "../../api";
import { getDefaultScalars, parseYaml, serializeToYaml } from "./yaml";

export function useConfigDialog(onClose: () => void) {
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

  return {
    yaml,
    setYaml,
    loading,
    saving,
    saveError,
    parseError,
    setParseError,
    activeDoc,
    setActiveDoc,
    runtimeInfo,
    fileInputRef,
    handleBackdrop,
    handleLoadFile,
    handleDownloadYaml,
    handleFileChange,
    handleSave,
  };
}
