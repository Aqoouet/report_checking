import { useEffect, useRef, useState } from "react";
import {
  cancelJob,
  fetchDefaultCheckPrompt,
  fetchRuntimeInfo,
  pollStatus,
  startCheck,
  validatePath,
  validateRange,
  validateRangeQuick,
  type StatusResponse,
  type ValidateRangeResponse,
} from "./api";
import PathField, { type PathFieldState } from "./components/PathField";
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
  const [pathState, setPathState] = useState<PathFieldState>("empty");
  const [pathMessage, setPathMessage] = useState("");
  const [isValidatingPath, setIsValidatingPath] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState<StatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [checkPrompt, setCheckPrompt] = useState("");
  const [runtimeLine, setRuntimeLine] = useState("Загрузка параметров ИИ…");
  const [isStopping, setIsStopping] = useState(false);
  const [serviceHelpOpen, setServiceHelpOpen] = useState(false);

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
        setRuntimeLine(
          `Модель: ${info.check_model} · фрагмент раздела до ~${info.doc_chunk_tokens.toLocaleString("ru-RU")} ток.`,
        );
      })
      .catch(() => {
        if (!cancelled) setRuntimeLine("Не удалось получить сведения о модели ИИ.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit =
    filePath.trim() !== "" && stage !== "starting" && !isValidating && !isValidatingPath;
  const canValidate =
    rangeInput.trim() !== "" && !isValidating && !isValidatingPath && stage === "idle";
  const canValidatePath =
    filePath.trim() !== "" && !isValidatingPath && !isValidating && stage === "idle";

  const handleRangeChange = (value: string) => {
    setRangeInput(value);
    if (rangeState !== "empty") {
      setRangeState("empty");
      setRangeError("");
      setRangeResult(null);
    }
  };

  const handleFilePathChange = (value: string) => {
    setFilePath(value);
    if (pathState !== "empty") {
      setPathState("empty");
      setPathMessage("");
    }
  };

  const handleValidatePath = async () => {
    if (!canValidatePath) return;
    setIsValidatingPath(true);
    setPathMessage("");
    try {
      const res = await validatePath(filePath.trim());
      if (res.valid) {
        setPathState("valid");
        setPathMessage(res.message);
      } else {
        setPathState("invalid");
        setPathMessage(res.message || "Путь недоступен");
      }
    } catch {
      setPathState("invalid");
      setPathMessage("Ошибка при проверке пути. Попробуйте ещё раз.");
    } finally {
      setIsValidatingPath(false);
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
        setIsStopping(false);
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
    setPathState("empty");
    setPathMessage("");
    setIsValidatingPath(false);
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
        <div className="label-row title-row">
          <h1 className="title">Проверка отчёта</h1>
          <button
            type="button"
            className="help-btn"
            onClick={() => setServiceHelpOpen((v) => !v)}
            aria-label="Справка по сервису"
            aria-expanded={serviceHelpOpen}
          >
            ?
          </button>
        </div>
        {serviceHelpOpen && (
          <div className="help-popup help-popup--service">
            <p className="help-popup__intro">
              Сервис анализирует текст отчёта и формирует файл с замечаниями по стилю и формулировкам.
            </p>
            <ul className="help-popup__list">
              <li><strong>Проверяется:</strong> текст разделов — стиль, формулировки, научный язык.</li>
              <li><strong>Не проверяется:</strong> рисунки, таблицы, формулы и другое нетекстовое содержимое.</li>
              <li><strong>Остаётся на нормоконтроле:</strong> оформление (шрифты, отступы, стили абзацев) — параметры, видимые только в Word.</li>
            </ul>
          </div>
        )}

        {isFormStage ? (
          <form onSubmit={handleSubmit} className="form">
            <PathField
              filePath={filePath}
              pathState={pathState}
              pathMessage={pathMessage}
              isValidating={isValidatingPath}
              canValidate={canValidatePath}
              onChange={handleFilePathChange}
              onValidate={handleValidatePath}
            />

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

            <details className="prompt-disclosure">
              <summary className="prompt-disclosure-summary">Информация о модели</summary>
              <p className="model-info-body" role="status">
                {runtimeLine}
              </p>
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
            onReset={reset}
          />
        )}
      </div>
    </div>
  );
}
