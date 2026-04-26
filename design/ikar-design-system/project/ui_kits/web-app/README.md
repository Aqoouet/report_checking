# Ikar Web App UI Kit

Click-thru recreation of the **Проверка отчёта** admin UI from `Aqoouet/report_checking@master:frontend`.

## What's here
- `index.html` — runs the full app (load it in a browser)
- `Atoms.jsx` — Button, Input, Field, Pill, Card, Spinner, ProgressBar, Logo
- `JobRow.jsx` — single job row with status pill, phase, progress, log toggle, cancel
- `ConfigDialog.jsx` — settings modal with field-level validation and help disclosures
- `App.jsx` — page shell + jobs list + click-thru behavior

## What you can do interactively
- Click **Проверить** → a new "processing" job appears in the queue
- Click **Отменить** on any pending/processing job → it transitions to `cancelled`
- Click **Показать лог** on a processing job → reveals the dark mono log panel
- Click **Настройки** → opens the wide config modal
- In the modal, click **✓** next to a field → fake validation, shows green success
- Click **?** next to any field → toggles inline help panel

## Coverage notes
This is a cosmetic recreation. We do **not** replicate:
- Real polling, SSE, or live log streaming
- YAML serialization / file upload-download
- Backend path validation (faked with a 600ms timer)
- Job phase progression beyond display

## Style source
All styles live in `index.html` `<style>` (extracted from `frontend/src/index.css`) plus tokens from `../../colors_and_type.css`. If you migrate this kit into production, replace the inline styles with the original `index.css` import.
