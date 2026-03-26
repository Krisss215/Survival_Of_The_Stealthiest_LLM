#!/usr/bin/env python3

"""
Generate a fresh text corpus for experiments in /home/efrat/test_corpus.

Behavior:
- Ensures the target directory exists.
- Removes any existing files in that directory.
- Creates 30 .txt files.
- Each file contains between 15 and 20 randomly sampled generic English sentences.

Usage:
    python3 generate_test_files.py
"""

import os
import random
from typing import List


TARGET_DIR = "/home/efrat/test_corpus"
NUM_FILES = 30
MIN_SENTENCES_PER_FILE = 15
MAX_SENTENCES_PER_FILE = 20


SENTENCES: List[str] = [
    "The quick brown fox jumps over the lazy dog.",
    "Data-driven experiments help us understand system behavior.",
    "Search-based software engineering explores large design spaces automatically.",
    "Carefully controlled benchmarks are essential for reproducible research.",
    "This sentence exists solely to provide test content for the corpus.",
    "Small, incremental changes can reveal interesting dynamic properties.",
    "The virtual machine is isolated from production systems for safety.",
    "Anomaly detection methods often rely on subtle statistical differences.",
    "Text files are convenient artifacts for many robustness experiments.",
    "Different workloads can trigger distinct resource-usage signatures.",
    "A good log format makes it easy to analyze results later.",
    "Randomization helps avoid overfitting to a single fixed pattern.",
    "This paragraph illustrates a simple example of synthetic text.",
    "Multiple sentences per file simulate more realistic documents.",
    "Robust detection should tolerate benign variation in the data.",
    "Each file in the corpus is independent and can be modified safely.",
    "Some experiments focus on I O patterns rather than content.",
    "It is important to separate training and evaluation data sets.",
    "Automated scripts reduce the chance of manual configuration errors.",
    "This final generic sentence closes the pool of example text.",
]


def ensure_empty_dir(path: str) -> None:
    """Create the directory if needed and remove any existing files inside it."""
    os.makedirs(path, exist_ok=True)

    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
            except OSError:
                pass


def generate_file_content() -> str:
    """Generate a multi-sentence text block for a single file."""
    num_sentences = random.randint(MIN_SENTENCES_PER_FILE, MAX_SENTENCES_PER_FILE)
    chosen = random.choices(SENTENCES, k=num_sentences)
    # Join sentences into paragraphs of a few sentences each for a more natural shape
    paragraphs = []
    idx = 0
    while idx < len(chosen):
        span = random.randint(2, 4)
        paragraph_sentences = chosen[idx : idx + span]
        paragraphs.append(" ".join(paragraph_sentences))
        idx += span
    return "\n\n".join(paragraphs) + "\n"


def main() -> None:
    print(f"Preparing fresh corpus directory at {TARGET_DIR!r} ...")
    ensure_empty_dir(TARGET_DIR)

    for i in range(1, NUM_FILES + 1):
        filename = f"doc_{i:02d}.txt"
        path = os.path.join(TARGET_DIR, filename)
        content = generate_file_content()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  wrote {path}")

    print(f"Done. Generated {NUM_FILES} files in {TARGET_DIR!r}.")


if __name__ == "__main__":
    main()

