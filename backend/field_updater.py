"""LibreOffice-based field updater for .docx files.

When Word documents use STYLEREF / SEQ / REF fields for automatic caption
numbering with chapter prefixes, python-docx reads the stale cached field
results instead of the computed values.  LibreOffice headless can open the
file, recompute all fields, and save a fresh copy so all subsequent parsing
sees correct values (e.g. "Рисунок 5-1" instead of "Рисунок Методы...-1").

Set env var LO_FIELD_UPDATE=0 to disable (e.g. if LibreOffice is not installed
or causes problems with a particular document).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_LO_ENABLED = os.getenv("LO_FIELD_UPDATE", "1").strip().lower() not in ("0", "false", "no", "off")


def update_docx_fields(file_path: str) -> str:
    """Return path to a .docx with all fields recomputed by LibreOffice.

    LibreOffice headless opens the file, recalculates every field (STYLEREF,
    SEQ, REF, …), and writes a fresh .docx to a temporary directory.

    Returns *file_path* unchanged when:
    - LO_FIELD_UPDATE=0
    - ``libreoffice`` binary not found
    - conversion times out (60 s) or fails for any reason

    The caller must NOT delete the returned path if it differs from
    *file_path*; the temporary directory is cleaned up by the caller via
    :func:`cleanup_updated_docx`.
    """
    if not _LO_ENABLED:
        return file_path

    try:
        out_dir = tempfile.mkdtemp(prefix="rc_lo_")
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--norestore",
                "--convert-to", "docx",
                "--outdir", out_dir,
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.warning(
                "LibreOffice field update failed (rc=%d): %s",
                result.returncode,
                result.stderr[:400],
            )
            shutil.rmtree(out_dir, ignore_errors=True)
            return file_path

        basename = os.path.splitext(os.path.basename(file_path))[0] + ".docx"
        updated = os.path.join(out_dir, basename)
        if not os.path.exists(updated):
            logger.warning("LibreOffice field update: output file not found at %s", updated)
            shutil.rmtree(out_dir, ignore_errors=True)
            return file_path

        logger.info("LibreOffice field update OK → %s", updated)
        return updated

    except FileNotFoundError:
        logger.info("libreoffice binary not found; skipping field update")
        return file_path
    except subprocess.TimeoutExpired:
        logger.warning("LibreOffice field update timed out after 60 s")
        return file_path
    except Exception as exc:
        logger.warning("LibreOffice field update unexpected error: %s", exc)
        return file_path


def cleanup_updated_docx(original_path: str, updated_path: str) -> None:
    """Remove the temporary directory created by :func:`update_docx_fields`.

    Safe to call even when *updated_path* == *original_path* (no-op).
    """
    if updated_path != original_path:
        shutil.rmtree(os.path.dirname(updated_path), ignore_errors=True)
