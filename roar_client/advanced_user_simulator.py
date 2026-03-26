#!/usr/bin/env python3

"""
Advanced Benign User Activity Simulator

Purpose:
    Generate human-like, benign text-editing activity on a dedicated test
    corpus for academic anomaly-detection research.

Behavior:
    - Targets ONLY: /home/efrat/test_corpus
    - On each step, picks a random .txt file in that directory tree.
    - Randomly performs one of three actions:
        * APPEND: add an editorial-style sentence at the end of the file.
        * UPDATE: replace a common word with a variant/synonym.
        * COMMENT: insert a timestamped note line at a random position.
    - Uses Gaussian-distributed delays between actions to mimic bursts
      and pauses in human activity.
    - Logs all actions to user_activity_log.csv so experiments are auditable.

Usage:
    cd /home/efrat/Roar-Attack-Challenge/roar_client
    python3 advanced_user_simulator.py
"""

from __future__ import annotations

import csv
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# =======================
# Configuration
# =======================

TARGET_DIR = "/home/efrat/test_corpus"
LOG_FILENAME = "user_activity_log.csv"

# Gaussian delay parameters (seconds)
DELAY_MEAN = 30.0
DELAY_STDDEV = 10.0
DELAY_MIN = 5.0

# File I/O retry behavior
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 0.5


# =======================
# Sentence & Word Pools
# =======================

EDITORIAL_SENTENCES: List[str] = [
    "Revised the introductory paragraph for clarity.",
    "Updated the main body to improve readability.",
    "Clarified the description of the experimental setup.",
    "Adjusted the wording in the second section.",
    "Refined the explanation of the evaluation metrics.",
    "Rephrased a sentence to avoid repetition.",
    "Added a short note about the methodology.",
    "Expanded the discussion of related work slightly.",
    "Inserted an example to illustrate the key idea.",
    "Smoothed the transition between two paragraphs.",
    "Rewrote a sentence to be more concise.",
    "Fixed a minor stylistic issue in the text.",
    "Improved the consistency of terminology.",
    "Adjusted punctuation to match the style guide.",
    "Reorganized a couple of sentences for better flow.",
    "Strengthened the concluding remarks.",
    "Simplified a complex sentence in the body.",
    "Clarified the intent of a supporting argument.",
    "Added a brief explanatory remark in the middle.",
    "Aligned the phrasing with earlier sections.",
    "Cleaned up redundant wording in a paragraph.",
    "Polished a sentence to read more naturally.",
    "Extended a remark with one extra detail.",
    "Tightened the language in the overview.",
    "Improved consistency between the summary and body.",
    "Provided a slightly more precise formulation.",
    "Balanced the length of two consecutive sentences.",
    "Reordered clauses to emphasize the main point.",
    "Made the description of the dataset clearer.",
    "Refined how the results section is introduced.",
    "Improved the explanation of the baseline scenario.",
    "Enhanced the description of the user simulator.",
    "Clarified the relationship between two concepts.",
    "Rewrote an example to make it more concrete.",
    "Made a subtle stylistic improvement in the text.",
    "Reframed a sentence in the active voice.",
    "Aligned the tense with the rest of the section.",
    "Elaborated on a previously brief observation.",
    "Improved the closing sentence of a paragraph.",
    "Made the terminology more consistent overall.",
    "Adjusted a phrase to reduce ambiguity.",
    "Rewrote a sentence to avoid a long subordinate clause.",
    "Clarified a reference to earlier material.",
    "Strengthened the link between two ideas.",
    "Inserted a short reminder of the main objective.",
    "Reordered two sentences for a more natural flow.",
    "Expanded a succinct remark into a full sentence.",
    "Calibrated the tone to be more neutral.",
    "Enhanced a description with a concrete detail.",
    "Polished the wording in the concluding paragraph.",
]

# Common word replacements for "UPDATE" actions.
# We replace the first occurrence found in the text.
WORD_REPLACEMENTS: Dict[str, str] = {
    " is ": " remains ",
    " the ": " this ",
    " data ": " dataset ",
    " experiment ": " study ",
    " experiments ": " studies ",
    " result ": " outcome ",
    " results ": " outcomes ",
    " test ": " evaluation ",
    " tests ": " evaluations ",
    " user ": " participant ",
    " users ": " participants ",
}


# =======================
# File Helpers with Retry
# =======================

def gaussian_delay() -> float:
    """Sample a delay value from a Gaussian, clamped to a minimum."""
    delay = random.gauss(DELAY_MEAN, DELAY_STDDEV)
    return max(DELAY_MIN, delay)


def list_text_files(root: str) -> List[str]:
    files: List[str] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".txt"):
                files.append(os.path.join(dirpath, name))
    return files


def read_file_with_retry(path: str) -> Optional[str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError as exc:
            print(f"[user-sim] Read failed ({attempt}/{MAX_RETRIES}) for {path}: {exc}")
            time.sleep(RETRY_BACKOFF_SECONDS)
    return None


def write_file_with_retry(path: str, data: str) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(data)
            return True
        except OSError as exc:
            print(f"[user-sim] Write failed ({attempt}/{MAX_RETRIES}) for {path}: {exc}")
            time.sleep(RETRY_BACKOFF_SECONDS)
    return False


def append_log_entry(
    base_dir: str,
    rel_path: str,
    action_type: str,
    content_added: str,
) -> None:
    """Append an action entry to user_activity_log.csv in TARGET_DIR."""
    log_path = os.path.join(base_dir, LOG_FILENAME)
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Ensure log directory exists
    os.makedirs(base_dir, exist_ok=True)

    new_file = not os.path.exists(log_path)
    try:
        with open(log_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(["timestamp", "file_path", "action_type", "content_added"])
            writer.writerow([timestamp, rel_path, action_type, content_added])
    except OSError as exc:
        print(f"[user-sim] Failed to write log entry: {exc}")


# =======================
# Action Implementations
# =======================

def do_append_action(abs_path: str, base_dir: str, text: str) -> bool:
    sentence = random.choice(EDITORIAL_SENTENCES)
    new_text = text
    if not new_text.endswith("\n"):
        new_text += "\n"
    new_text += sentence + "\n"

    if not write_file_with_retry(abs_path, new_text):
        return False

    rel_path = os.path.relpath(abs_path, base_dir)
    append_log_entry(base_dir, rel_path, "APPEND", sentence)
    print(f"[user-sim] APPEND on {rel_path}: {sentence!r}")
    return True


def do_update_action(abs_path: str, base_dir: str, text: str) -> bool:
    # Attempt to find and replace the first matching pattern.
    for needle, replacement in WORD_REPLACEMENTS.items():
        idx = text.find(needle)
        if idx != -1:
            new_text = text.replace(needle, replacement, 1)
            if not write_file_with_retry(abs_path, new_text):
                return False

            changed_fragment = f"{needle.strip()} -> {replacement.strip()}"
            rel_path = os.path.relpath(abs_path, base_dir)
            append_log_entry(base_dir, rel_path, "UPDATE", changed_fragment)
            print(f"[user-sim] UPDATE on {rel_path}: {changed_fragment}")
            return True

    # No replacement applied
    return False


def do_comment_action(abs_path: str, base_dir: str, text: str) -> bool:
    lines = text.splitlines(keepends=True)
    # Even if the file is empty, we can add a first "note" line.
    insert_idx = random.randint(0, len(lines)) if lines else 0

    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    note = f"[NOTE {ts}] User left a brief comment.\n"

    new_lines = lines[:insert_idx] + [note] + lines[insert_idx:]
    new_text = "".join(new_lines)

    if not write_file_with_retry(abs_path, new_text):
        return False

    rel_path = os.path.relpath(abs_path, base_dir)
    append_log_entry(base_dir, rel_path, "COMMENT", note.strip())
    print(f"[user-sim] COMMENT on {rel_path}: {note.strip()!r}")
    return True


def perform_random_action(abs_path: str, base_dir: str) -> None:
    text = read_file_with_retry(abs_path)
    if text is None:
        print(f"[user-sim] Skipping {abs_path}: could not read after retries.")
        return

    action = random.choice(["APPEND", "UPDATE", "COMMENT"])

    if action == "APPEND":
        do_append_action(abs_path, base_dir, text)
    elif action == "UPDATE":
        updated = do_update_action(abs_path, base_dir, text)
        if not updated:
            # fall back to a different benign action if no word was updated
            do_append_action(abs_path, base_dir, text)
    else:  # COMMENT
        do_comment_action(abs_path, base_dir, text)


# =======================
# Main loop
# =======================

def main() -> None:
    if not os.path.isdir(TARGET_DIR):
        raise SystemExit(
            f"TARGET_DIR does not exist or is not a directory: {TARGET_DIR}"
        )

    print(
        f"[user-sim] Starting advanced user simulator on {TARGET_DIR!r} "
        f"(mean delay={DELAY_MEAN}s, stddev={DELAY_STDDEV}s)"
    )

    try:
        while True:
            txt_files = list_text_files(TARGET_DIR)
            if not txt_files:
                print(f"[user-sim] No .txt files found under {TARGET_DIR}. Sleeping...")
                time.sleep(DELAY_MIN)
                continue

            target_file = random.choice(txt_files)
            perform_random_action(target_file, TARGET_DIR)

            delay = gaussian_delay()
            print(f"[user-sim] Sleeping for {delay:.1f} seconds.")
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\n[user-sim] Stopped by user.")


if __name__ == "__main__":
    main()

