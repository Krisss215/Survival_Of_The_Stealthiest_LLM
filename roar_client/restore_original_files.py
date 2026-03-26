#!/usr/bin/env python3

"""
Restore original text files in /home/efrat/test_corpus based on perturbation_log.csv.

This script is the inverse of text_perturbation_tool.py:
- It reads the log of character substitutions (perturbation_log.csv)
- Processes the log entries in reverse order (last change first)
- Reapplies the original characters at the recorded positions

Log format expected (CSV, produced by text_perturbation_tool.py):
    timestamp,relative_path,position,original_char,new_char
    2026-03-07T12:00:00Z,doc_01.txt,123,'a','b'

Characters are stored using repr(), so this script uses ast.literal_eval to
interpret them (handles whitespace and special characters correctly).

Usage:
    cd /home/efrat/Roar-Attack-Challenge/roar_client
    python3 restore_original_files.py
"""

import ast
import csv
import os
from dataclasses import dataclass
from typing import Dict, List


TARGET_DIR = "/home/efrat/test_corpus"
LOG_FILENAME = "perturbation_log.csv"


@dataclass
class LogEntry:
    """Single perturbation log entry."""

    rel_path: str
    position: int
    original_char: str
    new_char: str


def load_log_entries(base_dir: str, log_filename: str) -> List[LogEntry]:
    """Load and parse all perturbation log entries."""
    log_path = os.path.join(base_dir, log_filename)
    if not os.path.isfile(log_path):
        raise SystemExit(f"Log file not found: {log_path}")

    entries: List[LogEntry] = []
    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rel_path = row["relative_path"]
                position = int(row["position"])
                original_char = ast.literal_eval(row["original_char"])
                new_char = ast.literal_eval(row["new_char"])
            except Exception as exc:  # noqa: BLE001
                print(f"[restore] Skipping malformed row {row!r}: {exc}")
                continue

            # Ensure single-character strings
            if not isinstance(original_char, str) or len(original_char) != 1:
                print(f"[restore] Skipping row with invalid original_char: {row!r}")
                continue
            if not isinstance(new_char, str) or len(new_char) != 1:
                print(f"[restore] Skipping row with invalid new_char: {row!r}")
                continue

            entries.append(
                LogEntry(
                    rel_path=rel_path,
                    position=position,
                    original_char=original_char,
                    new_char=new_char,
                )
            )

    return entries


def restore_files(base_dir: str, entries: List[LogEntry]) -> None:
    """
    Restore files based on log entries, processed in reverse.

    For safety, we only change a character if the current character at that
    position matches the recorded new_char; otherwise we report a warning and
    leave it unchanged.
    """
    # Group entries by file for efficient file I/O
    entries_by_file: Dict[str, List[LogEntry]] = {}
    for entry in reversed(entries):  # reverse global order first
        entries_by_file.setdefault(entry.rel_path, []).append(entry)

    for rel_path, file_entries in entries_by_file.items():
        abs_path = os.path.join(base_dir, rel_path)
        if not os.path.isfile(abs_path):
            print(f"[restore] File missing, skipping: {abs_path}")
            continue

        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError as exc:  # noqa: BLE001
            print(f"[restore] Could not read {abs_path}: {exc}")
            continue

        if not text:
            continue

        chars = list(text)
        changed = 0

        for entry in file_entries:
            pos = entry.position
            if pos < 0 or pos >= len(chars):
                print(
                    f"[restore] Position out of range for {rel_path}: {pos} "
                    f"(len={len(chars)})"
                )
                continue

            current = chars[pos]
            if current != entry.new_char:
                # Likely already restored or file changed by other means
                print(
                    f"[restore] Mismatch in {rel_path} at {pos}: "
                    f"expected {entry.new_char!r}, found {current!r}. Skipping."
                )
                continue

            chars[pos] = entry.original_char
            changed += 1

        if changed == 0:
            print(f"[restore] No changes applied to {rel_path}")
            continue

        new_text = "".join(chars)
        try:
            with open(abs_path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(new_text)
            print(f"[restore] Restored {changed} character(s) in {rel_path}")
        except OSError as exc:  # noqa: BLE001
            print(f"[restore] Could not write {abs_path}: {exc}")


def main() -> None:
    if not os.path.isdir(TARGET_DIR):
        raise SystemExit(
            f"TARGET_DIR does not exist or is not a directory: {TARGET_DIR}"
        )

    print(f"[restore] Using TARGET_DIR={TARGET_DIR!r}")
    print(f"[restore] Reading log from {os.path.join(TARGET_DIR, LOG_FILENAME)!r}")

    entries = load_log_entries(TARGET_DIR, LOG_FILENAME)
    if not entries:
        print("[restore] No valid log entries found. Nothing to do.")
        return

    print(f"[restore] Loaded {len(entries)} log entries. Restoring files...")
    restore_files(TARGET_DIR, entries)
    print("[restore] Done.")


if __name__ == "__main__":
    main()

