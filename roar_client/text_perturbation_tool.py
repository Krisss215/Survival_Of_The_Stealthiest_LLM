#!/usr/bin/env python3
"""
Benign Text Perturbation Tool for Defensive Evaluation

This script introduces controlled, incremental drift into text files in a
designated test corpus directory. It is intended solely for robustness testing
of anomaly and fingerprinting-based detection systems in research contexts.

Behavior (high level):
- Targets ONLY /home/efrat/test_corpus
- Every STEPS_INTERVAL seconds, picks a random .txt file in that directory tree
- Performs CHARS_PER_STEP character-level substitutions in-place
- Keeps file size identical (substitutions only, no insertions/deletions)
- Logs every change to a CSV log so the experiment can be fully reversed later

The log format is:
timestamp,relative_path,position,original_char,new_char

To reverse, one can process the log in reverse chronological/log order and
rewrite each character from new_char back to original_char at the logged
position.
"""

import hashlib
import hmac
import os
import random
import re
import string
import time

from datetime import datetime
from typing import List, Optional, Tuple
from stealth_utils import is_file_in_use

# =======================
# Configuration Parameters
# =======================

# Directory containing ONLY the experimental corpus (safe to perturb)
TARGET_DIR = "/home/efrat/test_corpus"

# Initial (slow) seconds to wait between perturbation steps.
# This will be adapted dynamically based on detection feedback.
INITIAL_STEPS_INTERVAL = 20.0
# Minimum allowed interval so we never get too aggressive.
MIN_STEPS_INTERVAL = 0.2
# Current, dynamically adjusted interval (may change based on feedback).
STEPS_INTERVAL = INITIAL_STEPS_INTERVAL

# Number of character substitutions per step
CHARS_PER_STEP = 100

# Path of the perturbation log (relative to TARGET_DIR)
LOG_FILENAME = "perturbation_log.csv"


# =======================
# Utility Functions
# =======================

def list_text_files(root: str) -> List[str]:
    """Return a list of absolute paths to .txt files under root."""
    txt_files: List[str] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".txt"):
                txt_files.append(os.path.join(dirpath, name))
    return txt_files


def load_file_text(path: str) -> Optional[str]:
    """Read file as UTF-8 text (ignoring undecodable bytes). Return None if empty."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
    except OSError:
        return None
    if not data:
        return None
    return data


def write_file_text(path: str, data: str) -> bool:
    """Write UTF-8 text back to file. Return True on success."""
    try:
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(data)
        return True
    except OSError:
        return False

CIPHER_KEY = b"Thesis_Isolated_Lab_Secret_Key_2026"
ALPHANUM = string.ascii_letters + string.digits
DIGITS = string.digits
LETTERS = string.ascii_letters


def keyed_fpe_substitute(original: str, file_rel_path: str, position: int) -> str:
    if original not in ALPHANUM:
        return original

    nonce = f"{file_rel_path}:{position}".encode("utf-8")
    digest = hmac.new(CIPHER_KEY, nonce, hashlib.sha256).digest()
    shift_seed = int.from_bytes(digest[:4], "big")

    alphabet = LETTERS if original in LETTERS else DIGITS
    idx = alphabet.index(original)
    step = (shift_seed % (len(alphabet) - 1)) + 1
    new_idx = (idx + step) % len(alphabet)
    return alphabet[new_idx]


def select_positions_semantic(text: str, count: int) -> List[int]:
    candidate_positions: List[int] = []
    for match in re.finditer(r"\b[A-Za-z0-9]{4,}\b", text):
        start, end = match.span()
        for pos in range(start, end):
            candidate_positions.append(pos)

    if not candidate_positions:
        candidate_positions = [
            i for i, ch in enumerate(text) if ch in ALPHANUM
        ]

    if not candidate_positions:
        return []

    if count >= len(candidate_positions):
        return candidate_positions

    return random.sample(candidate_positions, count)


def append_log_entry(
    base_dir: str,
    log_filename: str,
    rel_path: str,
    position: int,
    original_char: str,
    new_char: str,
) -> None:
    log_path = os.path.join(base_dir, log_filename)
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    orig_repr = repr(original_char)
    new_repr = repr(new_char)

    line = f"{timestamp},{rel_path},{position},{orig_repr},{new_repr}\n"

    try:
        new_file = not os.path.exists(log_path)
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            if new_file:
                f.write("timestamp,relative_path,position,original_char,new_char\n")
            f.write(line)
    except OSError:
        pass


def perturb_file(
    abs_path: str,
    base_dir: str,
    chars_per_step: int,
) -> Optional[int]:
    text = load_file_text(abs_path)
    if text is None:
        return None

    if not text:
        return 0

    positions = select_positions_semantic(text, chars_per_step)
    if not positions:
        return 0

    chars = list(text)
    rel_path = os.path.relpath(abs_path, base_dir)

    modified_count = 0
    for pos in positions:
        original = chars[pos]
        replacement = keyed_fpe_substitute(original, rel_path, pos)
        if replacement == original:
            continue
        chars[pos] = replacement
        append_log_entry(
            base_dir=base_dir,
            log_filename=LOG_FILENAME,
            rel_path=rel_path,
            position=pos,
            original_char=original,
            new_char=replacement,
        )
        modified_count += 1

    if modified_count == 0:
        return 0

    new_text = "".join(chars)
    success = write_file_text(abs_path, new_text)
    if not success:
        return None

    return modified_count

def perturb_file(
    abs_path: str,
    base_dir: str,
    chars_per_step: int,
) -> Optional[int]:
    """
    Apply up to `chars_per_step` character substitutions in the given file.

    Returns the number of characters actually modified, or None on failure.
    """
    text = load_file_text(abs_path)
    if text is None:
        return None

    if not text:
        return 0

    positions = select_positions(text, chars_per_step)
    if not positions:
        return 0

    # Convert to list for in-place modification
    chars = list(text)
    rel_path = os.path.relpath(abs_path, base_dir)

    modified_count = 0
    for pos in positions:
        original = chars[pos]
        replacement = choose_replacement_char(original)
        if replacement == original:
            # If for any reason we didn't get a different char, skip this position
            continue
        chars[pos] = replacement
        append_log_entry(
            base_dir=base_dir,
            log_filename=LOG_FILENAME,
            rel_path=rel_path,
            position=pos,
            original_char=original,
            new_char=replacement,
        )
        modified_count += 1

    if modified_count == 0:
        return 0

    new_text = "".join(chars)
    success = write_file_text(abs_path, new_text)
    if not success:
        return None

    return modified_count


# =======================
# Workload Burst + Main Loop
# =======================

def run_workload_burst(
    chars_per_step: int,
    delay: float,
    test_duration_sec: float = 10.0,
) -> int:
    """
    Run a fixed-duration perturbation workload burst.

    This function does not read detection signals; it only applies benign
    substitutions and returns the total number of modified characters.
    """
    total_modified = 0
    burst_start = time.time()

    while time.time() - burst_start < test_duration_sec:
        txt_files = list_text_files(TARGET_DIR)
        if not txt_files:
            print(
                "[TextPerturbationTool] No .txt files found under "
                f"{TARGET_DIR}. Sleeping for {delay}s..."
            )
            time.sleep(delay)
            continue

        chosen_file = random.choice(txt_files)
        if is_file_in_use(chosen_file):
            print(
                f"[TextPerturbationTool] File in use by user, skipping for now... {chosen_file}"
            )
            time.sleep(delay)
            continue

        modified = perturb_file(
            abs_path=chosen_file,
            base_dir=TARGET_DIR,
            chars_per_step=chars_per_step,
        )

        if modified is None:
            print(f"[TextPerturbationTool] Failed to modify file: {chosen_file}")
        elif modified == 0:
            print(
                f"[TextPerturbationTool] No suitable characters modified in: "
                f"{chosen_file}"
            )
        else:
            total_modified += modified
            print(
                f"[TextPerturbationTool] Modified {modified} char(s) in: "
                f"{chosen_file}"
            )

        print(f"[TextPerturbationTool] Sleeping for {delay}s")
        time.sleep(delay)

    return total_modified


def main() -> None:

    if not os.path.isdir(TARGET_DIR):
        raise SystemExit(
            f"TARGET_DIR does not exist or is not a directory: {TARGET_DIR}"
        )

    print(
        f"[TextPerturbationTool] Starting with TARGET_DIR={TARGET_DIR}, "
        f"STEPS_INTERVAL={STEPS_INTERVAL}s, CHARS_PER_STEP={CHARS_PER_STEP}"
    )
    print(
        f"[TextPerturbationTool] Logging changes to "
        f"{os.path.join(TARGET_DIR, LOG_FILENAME)}"
    )

    try:
        while True:
            modified_in_burst = run_workload_burst(
                chars_per_step=CHARS_PER_STEP,
                delay=STEPS_INTERVAL,
                test_duration_sec=10.0,
            )
            print(
                f"[TextPerturbationTool] Burst complete. "
                f"Total modified chars: {modified_in_burst}"
            )
    except KeyboardInterrupt:
        print("\n[TextPerturbationTool] Stopped by user.")


if __name__ == "__main__":
    main()
