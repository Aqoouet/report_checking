# Results of investigation: Firefox cannot connect to `localhost:5173`

## Symptoms
- Firefox error: cannot establish connection to `localhost:5173`.
- `docker compose ps` showed both app containers restarting:
  - `report-checker-frontend`
  - `report-checker-backend`

## Root cause
- Project files and directories had restrictive ownership/permissions:
  - owner/group: `root:root`
  - mode: `1750` (including sticky bit `T`) on key paths and files.
- Containers run as non-root users, so they could not read required files.

## Evidence
- Frontend logs:
  - `open() "/etc/nginx/conf.d/default.conf" failed (13: Permission denied)`
- Backend logs:
  - `PermissionError: [Errno 13] Permission denied: '/app/main.py'`
- Permission check examples:
  - project root: `drwxr-x--T 1750 root:root`
  - `backend/main.py`: `-rwxr-x--T 1750 root:root`
  - `frontend/nginx.conf`: `-rwxr-x--T 1750 root:root`

## Why `5173` was unavailable
- In `docker-compose.yml`, frontend maps `${APP_PORT:-5173}:8080`.
- Frontend container failed to start (permission denied), so no process bound to host port `5173`.

## Suggested recovery (no code changes)
```bash
cd /filer/users/rymax1e/MRO/report_checking
sudo chown -R "$USER":"$USER" .
find . -type d -exec chmod 755 {} \;
find . -type f -exec chmod 644 {} \;
chmod +x rebuild-back-front.sh
docker compose up -d --build
docker compose ps
```
