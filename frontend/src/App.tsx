import { useState } from "react";
import { startCheckNew } from "./api";
import heroImage from "./assets/hero.png";
import { Icon } from "./components/Icon";
import ConfigDialog from "./components/ConfigDialog";
import JobQueueList from "./components/JobQueueList";
import "./index.css";

export default function App() {
  const [configOpen, setConfigOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");

  const handleCheck = async () => {
    setStarting(true);
    setStartError("");
    try {
      await startCheckNew();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="page">
      <div className="app-shell">
        <section className="hero-panel">
          <div className="hero-panel__main">
            <div className="brand-lockup">
              <img className="brand-lockup__logo" src="/logo-ikar.svg" alt="ИКАР" />
              <div className="brand-lockup__meta">Система проверки технических отчётов</div>
            </div>

            <div className="hero-eyebrow">Report Control Node</div>
            <h1 className="title title--hero">Проверка отчёта</h1>
            <p className="hero-lede">
              Конфигурируйте пайплайн, запускайте проверку и отслеживайте состояние задач в
              едином операторском интерфейсе.
            </p>

            <div className="action-row action-row--hero">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => setConfigOpen(true)}
              >
                <Icon name="i-gear" className="btn__icon" />
                <span>Настройки</span>
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleCheck}
                disabled={starting}
              >
                <Icon name={starting ? "i-spark" : "i-play"} className="btn__icon" />
                <span>{starting ? "Запускаем…" : "Проверить"}</span>
              </button>
            </div>

            {startError && <div className="start-error">{startError}</div>}
          </div>

          <aside className="hero-panel__aside">
            <div className="hero-visual">
              <img src={heroImage} alt="" aria-hidden="true" />
            </div>
            <div className="ops-card">
              <div className="ops-card__eyebrow">Pipeline</div>
              <div className="ops-card__title">Поток обработки</div>
              <div className="ops-card__list">
                <div className="ops-card__item">
                  <Icon name="i-document" className="ops-card__icon" />
                  <span>Документ и диапазоны секций</span>
                </div>
                <div className="ops-card__item">
                  <Icon name="i-spark" className="ops-card__icon" />
                  <span>LLM-проверка, валидация и суммаризация</span>
                </div>
                <div className="ops-card__item">
                  <Icon name="i-folder" className="ops-card__icon" />
                  <span>Артефакты и журнал выполнения</span>
                </div>
              </div>
            </div>
          </aside>
        </section>

        <div className="card card--wide card--jobs">
          <div className="section-head">
            <div>
              <div className="jobs-section-title">Оперативная очередь</div>
              <div className="section-subtitle">Активные, ожидающие и завершённые задачи</div>
            </div>
            <div className="section-badge">
              <Icon name="i-terminal" className="section-badge__icon" />
              <span>Live Queue</span>
            </div>
          </div>

          <div className="jobs-section">
            <JobQueueList />
          </div>
        </div>
      </div>

      {configOpen && <ConfigDialog onClose={() => setConfigOpen(false)} />}
    </div>
  );
}
