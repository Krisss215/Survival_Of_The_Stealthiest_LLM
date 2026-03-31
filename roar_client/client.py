from os import path, remove
from json import dumps, loads
from multiprocessing import Process
from socket import AF_INET, SOCK_STREAM, socket
from subprocess import call
from time import sleep

from globals import get_config_path, update_existing_config
from rwpoc import run

TARGET_PATH = "/home/efrat/test_ransomware"


def listen_for_config_changes():
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 42666))
        sock.listen(1)

        while True:
            conn, addr = sock.accept()  # keep listening for new connections
            with conn:
                while True:
                    data = conn.recv(1024)  # listen for incoming data of connection
                    if not data:
                        break
                    new_config = loads(data.decode(encoding="utf-8"))
                    print("received", new_config)

                    # Handle detection-status-only messages separately to avoid
                    # touching the main ransomware config file.
                    if "detection_status" in new_config:
                        try:
                            # JSON so the optimizer can log threshold / raw score when the server sends them.
                            record = {
                                "detection_status": new_config["detection_status"]
                            }
                            for key in (
                                "anomaly_score",
                                "anomaly_score_threshold",
                                "threshold",
                                "score",
                            ):
                                if key in new_config:
                                    record[key] = new_config[key]
                            with open("detection_status.txt", "w", encoding="utf-8") as f:
                                f.write(dumps(record))
                            print(
                                f"Updated detection status to {new_config['detection_status']}"
                            )
                        except OSError as e:
                            print("Failed to update detection_status.txt:", e)
                    else:
                        update_existing_config(new_config)


def collect_device_fingerprint():
    call("./fingerprinter.sh")  # without option "-n <limit>", this will continuously collect FP


def kill_process(proc):
    print("kill Process", proc)
    proc.terminate()
    proc.join()
    print("killed Process", proc)


if __name__ == "__main__":
    config_path = get_config_path()
    if path.exists(config_path):
        remove(config_path)

    procs = []
    proc_config = Process(target=listen_for_config_changes)
    procs.append(proc_config)
    proc_config.start()

    proc_fp = Process(target=collect_device_fingerprint)
    procs.append(proc_fp)
    proc_fp.start()

    print("Waiting for initial config...")
    while not path.exists(config_path):
        sleep(1)

    try:
        while True:
            # Idle loop: keep client alive to listen for config changes
            # and keep the fingerprinter running, without triggering
            # encryption runs or RW done notifications.
            sleep(10)
    finally:
        print("finally")
        for proc in procs:
            if proc.is_alive():
                kill_process(proc)
            else:
                print("Process", proc, "already dead.")
