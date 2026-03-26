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

import os
import random
import string
import time
from datetime import datetime
from typing import List, Optional, Tuple
from stealth_utils import is_file_in_use
# Warm-up / Calibration Phase Settings
START_TIME = time.time()
WARMUP_DURATION = 120 # 2 minutes in seconds

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


def choose_replacement_char(original: str) -> str:
    """
    Choose a replacement character for a given original character.

    The replacement is chosen from a conservative alphabet to keep the text
    readable-ish, but is guaranteed to differ from the original where possible.
    """
    # Character classes we allow to be replaced
    letters_digits = string.ascii_letters + string.digits
    whitespace = {" ", "\t"}
    punctuation = string.punctuation

    if original in letters_digits:
        # Replace with a different letter/digit
        candidates = [c for c in letters_digits if c != original]
    elif original in whitespace:
        # Replace space/tab with the other option
        if original == " ":
            candidates = ["\t"]
        else:
            candidates = [" "]
    elif original in punctuation:
        # Replace with a different punctuation character
        candidates = [c for c in punctuation if c != original]
    else:
        # For other characters (including newlines), leave unchanged
        # Caller should avoid selecting these when possible
        return original

    return random.choice(candidates) if candidates else original


def select_positions(text: str, count: int) -> List[int]:
    """
    Select up to `count` positions in text suitable for substitution,
    avoiding newline characters to preserve basic formatting.
    """
    candidate_positions = [i for i, ch in enumerate(text) if ch not in ("\n", "\r")]
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
    """
    Append a single change to the CSV log.

    Fields:
    - timestamp (ISO 8601)
    - relative path (from base_dir)
    - position (0-based index in current file content)
    - original_char (repr-style, with backslash escapes)
    - new_char (repr-style)
    """
    log_path = os.path.join(base_dir, log_filename)
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Use repr() for characters so whitespace and special chars are unambiguous
    orig_repr = repr(original_char)
    new_repr = repr(new_char)

    line = f"{timestamp},{rel_path},{position},{orig_repr},{new_repr}\n"

    # Create log file if not exists; append otherwise.
    try:
        new_file = not os.path.exists(log_path)
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            if new_file:
                f.write("timestamp,relative_path,position,original_char,new_char\n")
            f.write(line)
    except OSError:
        # Logging failures should not crash the tool; we just skip this entry.
        pass


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
# Main Loop
# =======================

def main() -> None:
    global STEPS_INTERVAL

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

    detection_status_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "detection_status.txt"
    )

    # Explicitly clear any previous detection state so we always start
    # from "normal" (0) for a fresh crawling episode.
    try:
        with open(detection_status_path, "w", encoding="utf-8") as f:
            f.write("0")
        print("[TextPerturbationTool] Initialized detection_status.txt to 0")
    except OSError as e:
        print("[TextPerturbationTool] Failed to initialize detection_status.txt:", e)

    try:
        while True:
            # Calibration Phase: Let the system record the baseline without attacking
            if time.time() - START_TIME < WARMUP_DURATION:
                print(f"[TextPerturbationTool] Calibration phase active. Waiting for model to establish baseline...")
                time.sleep(10)
                continue # Skip the attack logic until warm-up is done
            # =======================
            # Feedback-based interval adjustment
            # =======================
            try:
                with open(detection_status_path, "r", encoding="utf-8") as f:
                    status = f.read().strip()
            except FileNotFoundError:
                # If the file is missing, treat as normal (0) so we continue
                # probing the threshold instead of aborting.
                status = "0"
            except OSError:
                status = "0"

            # Adaptive crawling logic:
            # - Normal (0): slowly speed up (shorter interval),
            #   but never below MIN_STEPS_INTERVAL.
            # - Anomaly (1): immediately back off with a big jump.
            if status == "1":
                STEPS_INTERVAL = STEPS_INTERVAL + 15.0
            else:
                STEPS_INTERVAL = max(MIN_STEPS_INTERVAL, STEPS_INTERVAL - 1.0)

            txt_files = list_text_files(TARGET_DIR)
            if not txt_files:
                print(
                    "[TextPerturbationTool] No .txt files found under "
                    f"{TARGET_DIR}. Sleeping for {STEPS_INTERVAL}s..."
                )
                time.sleep(STEPS_INTERVAL)
                continue

            chosen_file = random.choice(txt_files)
            # Stealth Check: Is the file currently open by the user?
            if is_file_in_use(chosen_file):
                print(f"[TextPerturbationTool] File in use by user, skipping to stay stealthy: {chosen_file}")
                # Sleep a little bit so we don't spam the CPU if all files are locked
                time.sleep(1) 
                continue
            modified = perturb_file(
                abs_path=chosen_file,
                base_dir=TARGET_DIR,
                chars_per_step=random.randint(1, 5),
            )

            if modified is None:
                print(
                    f"[TextPerturbationTool] Failed to modify file: {chosen_file}"
                )
            elif modified == 0:
                print(
                    f"[TextPerturbationTool] No suitable characters modified in: "
                    f"{chosen_file}"
                )
            else:
                print(
                    f"[TextPerturbationTool] Modified {modified} char(s) in: "
                    f"{chosen_file}"
                )

            print(
                f"[TextPerturbationTool] Sleeping for {STEPS_INTERVAL}s "
                f"(detection_status={status!r})"
            )
            # Add random jitter to evade periodicity detection
            jitter = random.uniform(-2.0, 5.0)
            actual_sleep = max(MIN_STEPS_INTERVAL, STEPS_INTERVAL + jitter)
            time.sleep(actual_sleep)
    except KeyboardInterrupt:
        print("\n[TextPerturbationTool] Stopped by user.")


if __name__ == "__main__":
    main()