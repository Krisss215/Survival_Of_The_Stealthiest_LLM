import os
import time
import json
import socket
import csv
from collections import deque

import numpy as np

from environment.anomaly_detection.anomaly_detection import detect_anomaly, get_anomaly_score
from environment.reward.abstract_reward import AbstractReward
from environment.settings import CLIENT_IP
from environment.state_handling import initialize_storage, set_prototype


FP_POLL_INTERVAL_SECONDS = 1.0
CLIENT_PORT = 42666

# Conservative manual threshold on the anomaly score.
# For IsolationForest, more negative scores usually indicate stronger anomalies.
START_TIME = None
IS_WARMUP = True
WARMUP_DURATION = 120  # 20 mins
baseline_scores = []
ANOMALY_SCORE_THRESHOLD = 0.05
ANOMALY_LOG_FILE = "anomaly_log.csv"

# After warmup, refresh the adaptive threshold from a sliding window every N samples
# (blended with the previous threshold to avoid sudden jumps).
THRESHOLD_UPDATE_EVERY_N = 30
THRESHOLD_BLEND = 0.4
post_warmup_score_window = deque(maxlen=THRESHOLD_UPDATE_EVERY_N)
POST_WARMUP_SAMPLE_COUNT = 0



def load_model_prototype_1():
    """
    Initialize storage and train the AD model using Prototype 1 logic.
    Mirrors the initialization in evaluate-AD.py.
    """
    initialize_storage()
    set_prototype("1")
    AbstractReward.prepare_reward_computation()


def read_latest_fingerprint(fp_path):
    """
    Read and parse the fingerprint from the given file path.
    Returns a numpy array of floats or None if parsing fails.
    """
    try:
        with open(fp_path, "r") as f:
            line = f.readline().strip()
    except OSError as exc:
        print(f"[live_ad_bridge] Error reading fingerprint file {fp_path}: {exc}")
        return None

    if not line:
        return None

    # Strip brackets and whitespace if present and split into floats
    cleaned = line.replace("[", "").replace("]", "").replace(" ", "")
    try:
        values = list(map(float, cleaned.split(",")))
    except ValueError as exc:
        print(f"[live_ad_bridge] Failed to parse fingerprint values from {fp_path}: {exc}")
        return None

    return np.asarray(values)


def send_detection_status(status, anomaly_score, anomaly_score_threshold):
    """
    Send a JSON message to the client over TCP (e.g. for detection_status.txt / research CSV).
    """
    payload = {
        "detection_status": int(status),
        "anomaly_score_threshold": float(anomaly_score_threshold),
        "anomaly_score": float(anomaly_score),
    }
    data = json.dumps(payload).encode("utf-8")

    try:
        with socket.create_connection((CLIENT_IP, CLIENT_PORT), timeout=2.0) as sock:
            sock.sendall(data)
    except OSError as exc:
        print(f"[live_ad_bridge] Failed to send payload={payload!r} to "
              f"{CLIENT_IP}:{CLIENT_PORT}: {exc}")


def append_anomaly_log(timestamp, score, threshold, is_anomaly):
    """
    Append one inference result row to anomaly_log.csv.
    """
    file_exists = os.path.exists(ANOMALY_LOG_FILE)
    with open(ANOMALY_LOG_FILE, "a", newline="") as csv_file:
        writer = csv.writer(csv_file)
        if not file_exists:
            writer.writerow(["timestamp", "score", "threshold", "is_anomaly"])
        writer.writerow([timestamp, score, threshold, is_anomaly])


def monitor_fingerprints():
    """
    Watch the storage/ directory for updates to fp-*.txt and run live AD inference.
    """
    global START_TIME, IS_WARMUP, baseline_scores, ANOMALY_SCORE_THRESHOLD
    global post_warmup_score_window, POST_WARMUP_SAMPLE_COUNT

    storage_dir = os.path.join(os.path.abspath(os.path.curdir), "storage")
    print(f"[live_ad_bridge] Monitoring fingerprints in: {storage_dir}")

    # Track last modification times to avoid re-processing the same file contents
    last_mtimes = {}

    while True:
        if not os.path.isdir(storage_dir):
            time.sleep(FP_POLL_INTERVAL_SECONDS)
            continue

        for name in os.listdir(storage_dir):
            if not name.startswith("fp-") or not name.endswith(".txt"):
                continue

            fp_path = os.path.join(storage_dir, name)
            try:
                mtime = os.path.getmtime(fp_path)
            except OSError:
                continue

            previous_mtime = last_mtimes.get(fp_path)
            if previous_mtime is not None and mtime <= previous_mtime:
                continue

            last_mtimes[fp_path] = mtime

            fp_vector = read_latest_fingerprint(fp_path)
            if fp_vector is None:
                continue

            if START_TIME is None:
                START_TIME = time.time()

            # Run inference using the continuous anomaly score helper
            score = get_anomaly_score(fp_vector)

            elapsed = time.time() - START_TIME
            if elapsed < WARMUP_DURATION:
                IS_WARMUP = True
                baseline_scores.append(score)
                is_anomaly = 0
                threshold_used = ANOMALY_SCORE_THRESHOLD
            else:
                if IS_WARMUP:
                    IS_WARMUP = False
                    if baseline_scores:
                        ANOMALY_SCORE_THRESHOLD = np.percentile(baseline_scores, 1)
                    post_warmup_score_window.clear()
                    POST_WARMUP_SAMPLE_COUNT = 0

                threshold_used = ANOMALY_SCORE_THRESHOLD
                if score >= ANOMALY_SCORE_THRESHOLD:
                    is_anomaly = 0
                else:
                    is_anomaly = 1

                post_warmup_score_window.append(float(score))
                POST_WARMUP_SAMPLE_COUNT += 1
                if (
                    POST_WARMUP_SAMPLE_COUNT % THRESHOLD_UPDATE_EVERY_N == 0
                    and len(post_warmup_score_window) >= THRESHOLD_UPDATE_EVERY_N
                ):
                    window = list(post_warmup_score_window)
                    p1 = np.percentile(window, 1)
                    ANOMALY_SCORE_THRESHOLD = (
                        THRESHOLD_BLEND * p1
                        + (1.0 - THRESHOLD_BLEND) * ANOMALY_SCORE_THRESHOLD
                    )

            print(f"[Adaptive AD] Status: {'WARMUP' if IS_WARMUP else 'ACTIVE'} | "
                  f"Score: {score:.4f} | Threshold (decision): {threshold_used:.4f} | "
                  f"Anomaly: {is_anomaly}")

            append_anomaly_log(time.time(), score, threshold_used, is_anomaly)

            if is_anomaly:
                print("=== LIVE AD WARNING: ANOMALY DETECTED (detection_status=1) ===")

            send_detection_status(is_anomaly, score, threshold_used)

        time.sleep(FP_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    print("[live_ad_bridge] Starting live anomaly detection bridge with Prototype 1.")
    load_model_prototype_1()
    monitor_fingerprints()

