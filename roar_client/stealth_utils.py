import os
import subprocess
from pathlib import Path

import psutil


def is_file_in_use(file_path: str) -> bool:
    """
    Return True if any running process currently has file_path open, else False.
    This is read-only observation: no locking or opening of the target file.
    """
    target = str(Path(file_path).resolve())

    # Fast path: inspect process open-file tables via psutil.
    # We only read metadata from /proc; we do not touch the target file itself.
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            for opened in proc.open_files() or []:
                # Resolve symlinks/relative paths for robust comparison.
                if os.path.realpath(opened.path) == target:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Process exited or cannot be inspected; skip safely.
            continue

    # Fallback: use lsof (also passive listing of open file descriptors).
    try:
        # -F n emits machine-friendly output (lines beginning with 'n' are names).
        result = subprocess.run(
            ["lsof", "-F", "n", "--", target],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        # Any filename record matching target means at least one process has it open.
        return any(
            line.startswith("n") and os.path.realpath(line[1:]) == target
            for line in result.stdout.splitlines()
        )
    except FileNotFoundError:
        # lsof not installed and psutil found nothing.
        return False