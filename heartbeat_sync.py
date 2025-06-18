import json
import time

def send_heartbeat():
    heartbeat = {
        "signal": "NEUROSYNC_HEARTBEAT",
        "timestamp": time.time()
    }
    with open("receiver_ping.json", "w") as f:
        json.dump(heartbeat, f)
    print("[NEUROSYNC] Heartbeat ping sent.")

if __name__ == "__main__":
    while True:
        send_heartbeat()
        time.sleep(3)