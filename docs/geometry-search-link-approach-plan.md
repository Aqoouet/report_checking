# Geometry Search Style Reuse

```bash
ssh rymax1e-wg
cd /filer/wps/scripts/Apps/Geometry_search
python3 - <<'PY'
from pathlib import Path
p = Path("web_service/handlers/handlers.go")
for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
    if any(k in line for k in ("local-file-link", "handleFileClick", "window.open(", "href=")):
        print(f"{i}: {line}")
PY
```

```python
# backend/app/path_mapper.py (add)
from pathlib import Path

def map_linux_to_windows(raw_path: str) -> str:
    path = (raw_path or "").strip()
    if not path:
        return path
    for win_prefix in _SORTED_KEYS:
        linux_prefix = _MAPPING[win_prefix]
        if path.lower().startswith(linux_prefix.lower().rstrip("/")):
            remainder = path[len(linux_prefix.rstrip("/")) :].lstrip("/")
            return win_prefix.rstrip("\\") + ("\\" + remainder.replace("/", "\\") if remainder else "")
    return path

def to_file_url(path: str) -> str:
    p = (path or "").strip()
    if len(p) >= 2 and p[1] == ":":
        return "file:///" + p.replace("\\", "/")
    if p.startswith("/"):
        return "file://" + p
    return ""
```

```python
# backend/app/jobs.py (add fields)
artifact_dir_windows: Optional[str] = None
artifact_dir_file_url: Optional[str] = None
```

```python
# backend/app/pipeline_orchestrator.py (set derived paths when artifact_dir is known)
from app.path_mapper import map_linux_to_windows, to_file_url

artifact_dir_str = str(artifact_dir)
artifact_dir_windows = map_linux_to_windows(artifact_dir_str)
artifact_dir_file_url = to_file_url(artifact_dir_windows if artifact_dir_windows != artifact_dir_str else artifact_dir_str)

_patch_job(
    job.id,
    artifact_dir=artifact_dir_str,
    artifact_dir_windows=artifact_dir_windows,
    artifact_dir_file_url=artifact_dir_file_url,
    log_path=log_path,
)
```

```python
# backend/app/routes/check.py (include new fields in list payload)
"artifact_dir": j.artifact_dir,
"artifact_dir_windows": j.artifact_dir_windows,
"artifact_dir_file_url": j.artifact_dir_file_url,
```

```ts
// frontend/src/api/types.ts (extend JobSummary)
artifact_dir: string | null;
artifact_dir_windows: string | null;
artifact_dir_file_url: string | null;
```

```tsx
// frontend/src/components/JobQueueList/JobRow.tsx (replace artifact button with plain text + link)
{isTerminal && job.artifact_dir && (
  <div className="job-artifact-text" title={job.artifact_dir_windows || job.artifact_dir}>
    <span>Сохранено: </span>
    {job.artifact_dir_file_url ? (
      <a
        href={job.artifact_dir_file_url}
        className="job-artifact-link"
        data-filepath={job.artifact_dir_windows || job.artifact_dir}
        onClick={(event) => {
          const win = window.open((event.currentTarget as HTMLAnchorElement).href, "_blank");
          if (!win) {
            event.preventDefault();
            navigator.clipboard?.writeText(job.artifact_dir_windows || job.artifact_dir || "");
          }
        }}
      >
        {job.artifact_dir_windows || job.artifact_dir}
      </a>
    ) : (
      <span>{job.artifact_dir_windows || job.artifact_dir}</span>
    )}
  </div>
)}
```

```css
/* frontend/src/index.css */
.job-artifact-text {
  margin-top: 6px;
  font-size: 0.78rem;
  color: #64748b;
  word-break: break-all;
}

.job-artifact-link {
  color: #64748b;
  text-decoration: none;
}

.job-artifact-link:hover {
  color: #3b82f6;
  text-decoration: underline;
}
```

```bash
# geometry search original read checklist
ssh rymax1e-wg
cd /filer/wps/scripts/Apps/Geometry_search
python3 - <<'PY'
from pathlib import Path
p = Path("web_service/handlers/handlers.go")
text = p.read_text(encoding="utf-8", errors="ignore")
anchors = ["local-file-link", "handleFileClick", "window.open(", "HYPERLINK(", "href="]
for a in anchors:
    print("\\n=== ", a, " ===")
    for i, line in enumerate(text.splitlines(), 1):
        if a in line:
            print(f"{i}: {line}")
PY
```

