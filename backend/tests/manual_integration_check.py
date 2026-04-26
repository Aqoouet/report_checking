"""
Manual integration harness for the running report-checker service.

Run from the repo root on the target server:

    python3 backend/tests/manual_integration_check.py

Default behavior:
- reads the prepared YAML config
- rejects unallowlisted input/output paths before submit
- prints the allowed writable roots

Optional rewrite/staging mode:

    python3 backend/tests/manual_integration_check.py --rewrite-paths

Rewrite mode:
- copies the input file into an allowlisted directory
- rewrites only input_docx_path and output_dir
- writes an exact .staged.yaml copy preserving comments and block formatting
- submits the full job and waits until it reaches a terminal state
"""

import argparse
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import yaml

ALLOWED_PREFIXES = (
    "/filer/users/",
    "/filer/wps/wp/",
)
ALLOWED_REWRITTEN_KEYS = frozenset(("input_docx_path", "output_dir", "model"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Submit a full integration check to the running report-checker service, "
            "wait for all stages to finish, and fail if the job fails or run.log "
            "contains ERROR lines."
        )
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:5173/api",
        help="Service API base URL. Default: %(default)s",
    )
    parser.add_argument(
        "--config",
        default="/home/rymax1e/report_checking/test_data/config (4).yaml",
        help="Prepared YAML config path on the server. Default: %(default)s",
    )
    parser.add_argument(
        "--staged-dir",
        default="/filer/users/rymax1e/report_checker_test_data",
        help=(
            "Writable allowlisted directory used when the input/output paths in the "
            "prepared config are outside the backend allowlist. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Seconds between status polls. Default: %(default)s",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=4 * 60 * 60,
        help="Hard timeout for the full run. Default: %(default)s",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Optional explicit X-Session-ID. Default: auto-generated",
    )
    parser.add_argument(
        "--rewrite-paths",
        action="store_true",
        help=(
            "Opt in to staging the input file into an allowlisted directory and "
            "rewriting input/output paths before submit. By default the script "
            "fails fast when the config uses unallowlisted paths."
        ),
    )
    return parser.parse_args()


def _is_allowed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _stage_docx(input_path: Path, staged_dir: Path) -> Path:
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staged_dir / input_path.name
    shutil.copy2(input_path, staged_path)
    return staged_path


def _replace_scalar_line(text: str, key: str, value: str) -> str:
    pattern = r"(^\s*{0}\s*:\s*).*$".format(re.escape(key))
    replaced, count = re.subn(pattern, r"\1{0}".format(value), text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("Could not rewrite key in YAML text: {0}".format(key))
    return replaced


def _write_staged_yaml_exact(
    original_text: str,
    config_path: Path,
    input_path: str,
    output_dir: str,
) -> Path:
    staged_text = _replace_scalar_line(original_text, "input_docx_path", input_path)
    staged_text = _replace_scalar_line(staged_text, "output_dir", output_dir)
    staged_path = config_path.parent / (config_path.stem + ".staged.yaml")
    staged_path.write_text(staged_text, encoding="utf-8")
    return staged_path


def _load_config(
    config_path: Path,
    staged_dir: Path,
    rewrite_paths: bool,
) -> Tuple[Dict[str, Any], Dict[str, Tuple[Any, Any]]]:
    original_text = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(original_text)
    if not isinstance(config, dict):
        raise ValueError(f"Config {config_path} did not parse to a mapping")
    original = dict(config)

    raw_input = str(config.get("input_docx_path") or "").strip()
    raw_output = str(config.get("output_dir") or "").strip()
    if not raw_input:
        raise ValueError("Config is missing input_docx_path")
    if not raw_output:
        raise ValueError("Config is missing output_dir")

    input_path = Path(raw_input)
    output_path = Path(raw_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input report not found: {input_path}")

    needs_rewrite = not _is_allowed(str(input_path)) or not _is_allowed(str(output_path))
    if needs_rewrite and not rewrite_paths:
        raise ValueError(
            "Config uses unallowlisted paths. input_docx_path={0}; output_dir={1}. "
            "Allowed prefixes: {2}".format(
                input_path,
                output_path,
                ", ".join(ALLOWED_PREFIXES),
            )
        )

    if needs_rewrite:
        staged_input = _stage_docx(input_path, staged_dir)
        config["input_docx_path"] = str(staged_input)
        config["output_dir"] = str(staged_dir)
        staged_yaml = _write_staged_yaml_exact(
            original_text,
            config_path,
            str(staged_input),
            str(staged_dir),
        )
    else:
        staged_yaml = config_path.parent / (config_path.stem + ".staged.yaml")
        staged_yaml.write_text(original_text, encoding="utf-8")

    rewritten = {}  # type: Dict[str, Tuple[Any, Any]]
    for key in sorted(set(original) | set(config)):
        before = original.get(key)
        after = config.get(key)
        if before != after:
            rewritten[key] = (before, after)

    unexpected = sorted(set(rewritten) - ALLOWED_REWRITTEN_KEYS)
    if unexpected:
        raise ValueError("Unexpected rewritten keys: {0}".format(", ".join(unexpected)))
    config["_staged_yaml_path"] = str(staged_yaml)
    return config, rewritten


def _request(
    base_url: str,
    session_id: str,
    method: str,
    path: str,
    data: Optional[Any] = None,
    timeout: float = 120.0,
) -> Tuple[int, Optional[Any]]:
    payload = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Session-ID": session_id,
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else None


def _lookup_artifact_dir(base_url: str, session_id: str, job_id: str) -> str:
    _, data = _request(base_url, session_id, "GET", "/jobs", timeout=30.0)
    if not isinstance(data, list):
        return ""
    for item in data:
        if isinstance(item, dict) and item.get("id") == job_id:
            return str(item.get("artifact_dir") or "")
    return ""


def main() -> int:
    args = _parse_args()
    session_id = args.session_id or f"manual-int-{uuid4()}"
    config_path = Path(args.config)
    staged_dir = Path(args.staged_dir)

    config, rewritten = _load_config(config_path, staged_dir, args.rewrite_paths)

    print(f"session_id={session_id}", flush=True)
    print(f"config_path={config_path}", flush=True)
    print(f"staged_yaml_path={config['_staged_yaml_path']}", flush=True)
    print(f"effective_input={config['input_docx_path']}", flush=True)
    print(f"effective_output={config['output_dir']}", flush=True)
    if "output_dir" in rewritten:
        print(
            "allowed_output_prefixes={0}".format(", ".join(ALLOWED_PREFIXES)),
            flush=True,
        )
    if rewritten:
        print("rewritten_keys.begin", flush=True)
        for key in sorted(rewritten):
            before, after = rewritten[key]
            print(
                json.dumps(
                    {"key": key, "before": before, "after": after},
                    ensure_ascii=False,
                ),
                flush=True,
            )
        print("rewritten_keys.end", flush=True)
    else:
        print("rewritten_keys.none", flush=True)

    submit_config = dict(config)
    staged_yaml_path = str(submit_config.pop("_staged_yaml_path"))
    submit_config["_original_yaml"] = Path(staged_yaml_path).read_text(encoding="utf-8")
    status, data = _request(args.base_url, session_id, "POST", "/config", submit_config)
    print(f"config_status={status} body={json.dumps(data, ensure_ascii=False)}", flush=True)

    status, data = _request(args.base_url, session_id, "POST", "/check", {})
    if not isinstance(data, dict) or "job_id" not in data:
        raise RuntimeError(f"Unexpected /check response: {data!r}")
    job_id = str(data["job_id"])
    print(f"job_id={job_id}", flush=True)
    print(f"queue_position={data.get('queue_position')}", flush=True)

    started = time.monotonic()
    final: Optional[Dict[str, Any]] = None

    while time.monotonic() - started < args.timeout_seconds:
        time.sleep(args.poll_interval)
        _, status_data = _request(args.base_url, session_id, "GET", f"/status/{job_id}", timeout=30.0)
        if not isinstance(status_data, dict):
            raise RuntimeError(f"Unexpected /status response: {status_data!r}")
        final = status_data
        summary = {
            key: status_data.get(key)
            for key in (
                "status",
                "phase",
                "current_checkpoint_name",
                "checkpoint_sub_current",
                "checkpoint_sub_total",
                "error",
            )
        }
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if status_data.get("status") in {"done", "error", "cancelled"}:
            break
    else:
        raise TimeoutError(
            f"Job did not finish within {args.timeout_seconds} seconds. "
            f"Last status: {json.dumps(final or {}, ensure_ascii=False)}"
        )

    assert final is not None
    artifact_dir = _lookup_artifact_dir(args.base_url, session_id, job_id)
    print(f"artifact_dir={artifact_dir}", flush=True)

    _, log_payload = _request(args.base_url, session_id, "GET", f"/result_log/{job_id}", timeout=30.0)
    if not isinstance(log_payload, dict):
        raise RuntimeError(f"Unexpected /result_log response: {log_payload!r}")
    log_text = str(log_payload.get("log") or "")

    print("run.log.begin", flush=True)
    print(log_text, flush=True)
    print("run.log.end", flush=True)

    status_name = str(final.get("status") or "")
    if status_name != "done":
        print(f"FAIL: job finished with status={status_name}", file=sys.stderr)
        return 2
    if "ERROR" in log_text:
        print("FAIL: run.log contains ERROR", file=sys.stderr)
        return 3

    print("PASS: job reached done and run.log contains no ERROR", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
