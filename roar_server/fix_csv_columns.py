#!/usr/bin/env python3
"""
Fix CSV files in __data/original_dataset by removing alarmtimer and cachefiles columns,
then selecting exactly the 91 columns in ALL_CSV_HEADERS order (handles duplicate names).
"""

import os
import sys

import pandas as pd
#
# Import after potential cwd change
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from environment.settings import ALL_CSV_HEADERS

DATA_DIR = "./__data/original_dataset"
COLUMNS_TO_DROP = [
    "alarmtimer:alarmtimer_fired",
    "alarmtimer:alarmtimer_start",
    "cachefiles:cachefiles_create",
    "cachefiles:cachefiles_lookup",
    "cachefiles:cachefiles_mark_active",
]
EXPECTED_HEADERS = [h.strip() for h in ALL_CSV_HEADERS.split(",")]
EXPECTED_COLUMNS = len(EXPECTED_HEADERS)  # 91


def select_columns_in_order(df, expected_headers):
    """Select columns from df in the order of expected_headers. Handles pandas duplicate
    suffixes (.1, .2) when CSV has duplicate column names."""
    remaining = list(df.columns)
    result = []
    for name in expected_headers:
        found = None
        for i, col in enumerate(remaining):
            if col == name or (isinstance(col, str) and col.startswith(name + ".")):
                found = i
                break
        if found is None:
            raise ValueError(f"No column matching expected header {name!r}. Have: {remaining[:5]}...")
        result.append(remaining.pop(found))
    return df[result]


def main():
    if not os.path.isdir(DATA_DIR):
        print(f"Error: Directory not found: {DATA_DIR}")
        sys.exit(1)

    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    if not csv_files:
        print(f"No CSV files found in {DATA_DIR}")
        sys.exit(0)

    for filename in sorted(csv_files):
        path = os.path.join(DATA_DIR, filename)
        df = pd.read_csv(path)
        before = len(df.columns)

        # Drop the 5 columns if present (may be named exactly or with .1 suffix)
        to_drop = [c for c in df.columns if c in COLUMNS_TO_DROP or
                   any(c == d or c.startswith(d + ".") for d in COLUMNS_TO_DROP)]
        if to_drop:
            df = df.drop(columns=to_drop, errors="ignore")

        # Select exactly the 91 columns in ALL_CSV_HEADERS order
        df = select_columns_in_order(df, EXPECTED_HEADERS)
        after = len(df.columns)

        if after != EXPECTED_COLUMNS:
            print(f"{filename}: expected {EXPECTED_COLUMNS} columns, got {after}")
            sys.exit(1)

        df.to_csv(path, index=False)
        print(f"{filename}: {before} -> {after} columns (dropped 5, selected {EXPECTED_COLUMNS})")

    print(f"Done. All files have {EXPECTED_COLUMNS} columns.")


if __name__ == "__main__":
    main()
