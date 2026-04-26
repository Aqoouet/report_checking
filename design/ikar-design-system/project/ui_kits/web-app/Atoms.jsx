// Ikar UI Kit — atoms (Buttons, Inputs, Pill, Card, Spinner)
// Plain Babel JSX — exposes components on window for cross-script use.

const Button = ({ variant = "primary", size, children, disabled, onClick }) => {
  const cls = ["btn", `btn--${variant}`, size && `btn--${size}`].filter(Boolean).join(" ");
  return <button type="button" className={cls} disabled={disabled} onClick={onClick}>{children}</button>;
};

const Input = ({ value, onChange, state, placeholder, readOnly }) => {
  const cls = ["input", state && `input--${state}`, readOnly && "input--readonly"].filter(Boolean).join(" ");
  return <input className={cls} value={value} placeholder={placeholder} readOnly={readOnly}
    onChange={e => onChange && onChange(e.target.value)} />;
};

const Field = ({ label, children, hint, error }) => (
  <div className="field">
    <label className="label">{label}</label>
    {children}
    {hint && <div className="path-ok-hint">{hint}</div>}
    {error && <div className="range-error">{error}</div>}
  </div>
);

const Pill = ({ status, children }) => (
  <span className={`job-status job-status--${status}`}>{children}</span>
);

const Card = ({ wide, children }) => (
  <div className={`card${wide ? " card--wide" : ""}`}>{children}</div>
);

const Spinner = ({ size = 20 }) => (
  <span style={{
    width: size, height: size, display: "inline-block",
    border: "2px solid var(--ink-600)", borderTopColor: "var(--ikar-orange-500)",
    borderRadius: "50%", animation: "spin .7s linear infinite"
  }} />
);

const ProgressBar = ({ pct }) => (
  <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
);

const Logo = ({ size = 28 }) => (
  <img src="../../assets/logo.svg" alt="Ikar" style={{ width: size, height: "auto" }} />
);

Object.assign(window, { Button, Input, Field, Pill, Card, Spinner, ProgressBar, Logo });
