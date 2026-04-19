import { useEffect, useRef, useState } from "react";
import {
  cancelJob,
  fetchDefaultCheckPrompt,
  fetchRuntimeInfo,
  pollStatus,
  startCheck,
  validateRange,
  validateRangeQuick,
  type StatusResponse,
  type ValidateRangeResponse,
} from "./api";
import RangeField, { type RangeState } from "./components/RangeField";
import ProcessingView from "./components/ProcessingView";
import ResultView, { type TerminalStage } from "./components/ResultView";
import "./index.css";

type Stage = "idle" | "starting" | "processing" | TerminalStage;

export default function App() {
  const [filePath, setFilePath] = useState("");
  const [rangeInput, setRangeInput] = useState("");
  const [rangeState, setRangeState] = useState<RangeState>("empty");
  const [rangeResult, setRangeResult] = useState<ValidateRangeResponse | null>(null);
  const [rangeError, setRangeError] = useState("");
  const [isValidating, setIsValidating] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<StatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [checkPrompt, setCheckPrompt] = useState("");
  const [runtimeLine, setRuntimeLine] = useState("Загрузка параметров ИИ…");
  const [isStopping, setIsStopping] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDefaultCheckPrompt()
      .then((text) => {
        if (!cancelled) setCheckPrompt(text);
      })
      .catch(() => {
        /* backend default will apply if empty */
      });
    fetchRuntimeInfo()
      .then((info) => {
        if (cancelled) return;
        const ctx =
          info.context_tokens != null
            ? `контекст ~${info.context_tokens.toLocaleString("ru-RU")} ток.`
            : "контекст: нет данных от LM Studio";
        setRuntimeLine(
          `Модель: ${info.check_model} · ${ctx} · фрагмент раздела до ~${info.doc_chunk_tokens.toLocaleString("ru-RU")} ток.`,
        );
      })
      .catch(() => {
        if (!cancelled) setRuntimeLine("Не удалось получить сведения о модели ИИ.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit = filePath.trim() !== "" && stage !== "starting" && !isValidating;
  const canValidate = rangeInput.trim() !== "" && !isValidating && stage === "idle";

  const handleRangeChange = (value: string) => {
    setRangeInput(value);
    if (rangeState !== "empty") {
      setRangeState("empty");
      setRangeError("");
      setRangeResult(null);
    }
  };

  const handleValidate = async () => {
    if (!canValidate) return;
    setIsValidating(true);
    setRangeState("validating");
    setRangeError("");
    try {
      const res = await validateRange(rangeInput.trim());
      if (!res.valid) {
        setRangeResult(res);
        setRangeState("invalid");
        if (res.range_message) {
          setRangeError(res.range_message);
        } else if (res.server_error) {
          setRangeError("Не удалось обработать запрос. Проверьте доступность сервиса ИИ.");
        } else if (res.suggestion) {
          setRangeError(`Неверный диапазон. Возможное исправление: ${res.suggestion}`);
        } else {
          setRangeError("Неверный диапазон. Проверьте формат.");
        }
      } else {
        setRangeResult(res);
        setRangeState("valid");
      }
    } catch {
      setRangeState("invalid");
      setRangeError("Ошибка при валидации диапазона. Попробуйте ещё раз.");
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setRangeError("");

    if (rangeInput.trim() && rangeState !== "valid") {
      setIsValidating(true);
      try {
        const res = await validateRangeQuick(rangeInput.trim());
        setIsValidating(false);
        if (!res.valid) {
          setRangeState("invalid");
          setRangeError(
            res.suggestion
              ? `Неверный диапазон: ${res.suggestion}`
              : "Неверный формат диапазона. Проверьте ввод или нажмите «Валидировать».",
          );
          return;
        }
        setRangeResult(res);
        setRangeState("valid");
        await _runCheck(res);
      } catch {
        setIsValidating(false);
        await _runCheck(null);
      }
      return;
    }

    await _runCheck(rangeState === "valid" ? rangeResult : null);
  };

  const _runCheck = async (rangeRes: ValidateRangeResponse | null) => {
    setStage("starting");
    setErrorMsg("");
    try {
      const { job_id } = await startCheck(
        filePath.trim(),
        rangeRes?.valid ? rangeRes : undefined,
        checkPrompt,
      );
      setJobId(job_id);
      setIsStopping(false);
      setStage("processing");
      pollLoop(job_id);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStage("error");
    }
  };

  const pollLoop = (id: string, opts?: { onTerminal?: () => void }) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const s = await pollStatus(id);
        setProgress(s);
        if (s.status === "done" || s.status === "cancelled" || s.status === "error") {
          clearInterval(intervalRef.current!);
          intervalRef.current = null;
          opts?.onTerminal?.();
          if (s.status === "error") {
            setErrorMsg(s.error ?? "Неизвестная ошибка");
          }
          setStage(s.status as TerminalStage);
        }
      } catch {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        opts?.onTerminal?.();
        setErrorMsg("Потеряна связь с сервером");
        setStage("error");
      }
    }, 1500);
  };

  const handleStop = async () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsStopping(true);
    try {
      await cancelJob(jobId);
    } catch {
      // best effort
    }
    pollLoop(jobId, { onTerminal: () => setIsStopping(false) });
  };

  const reset = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setFilePath("");
    setRangeInput("");
    setRangeState("empty");
    setRangeResult(null);
    setRangeError("");
    setIsValidating(false);
    setStage("idle");
    setJobId("");
    setProgress(null);
    setErrorMsg("");
    setIsStopping(false);
  };

  const isFormStage = stage === "idle" || stage === "starting";

  return (
    <div className="page">
      <div className="card">
        <h1 className="title">Проверка отчёта</h1>
        <p className="subtitle">
          Укажите путь к файлу отчёта (.docx) — система проверит стиль изложения
          и сформирует текстовый отчёт об ошибках.
        </p>

        <p className="runtime-meta" role="status">
          {runtimeLine}
        </p>

        {isFormStage ? (
          <form onSubmit={handleSubmit} className="form">
            <div className="field">
              <label className="label" htmlFor="filepath">
                Путь к файлу
              </label>
              <input
                id="filepath"
                className="input"
                type="text"
                placeholder="P:\…\отчёт.docx или /filer/wps/wp/…/отчёт.docx"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                required
                autoComplete="off"
                spellCheck={false}
              />
              <span className="hint">
                Укажите путь к файлу в проектной папке на диске <code>P:</code> или в{" "}
                <code>/filer/wps/wp</code>. Принимаются только файлы .docx.
              </span>
            </div>

            <RangeField
              rangeInput={rangeInput}
              rangeState={rangeState}
              rangeResult={rangeResult}
              rangeError={rangeError}
              isValidating={isValidating}
              canValidate={canValidate}
              onChange={handleRangeChange}
              onValidate={handleValidate}
            />

            <details className="prompt-disclosure">
              <summary className="prompt-disclosure-summary">Промпт проверки</summary>
              <textarea
                className="prompt-textarea"
                value={checkPrompt}
                onChange={(e) => setCheckPrompt(e.target.value)}
                rows={14}
                spellCheck={false}
                aria-label="Промпт проверки"
              />
            </details>

            <button
              type="submit"
              className="btn btn--primary"
              disabled={!canSubmit}
            >
              {isValidating
                ? "Проверяем диапазон…"
                : stage === "starting"
                  ? "Запускаем…"
                  : "Проверить"}
            </button>
          </form>
        ) : stage === "processing" ? (
          <ProcessingView progress={progress} onStop={handleStop} isStopping={isStopping} />
        ) : (
          <ResultView
            stage={stage as TerminalStage}
            jobId={jobId}
            errorMsg={errorMsg}
            totalCheckpoints={progress?.total_checkpoints ?? 0}
            onReset={reset}
          />
        )}
      </div>
    </div>
  );
}
