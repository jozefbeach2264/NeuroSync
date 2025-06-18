import json
import time

class LogPulse:
    def __init__(self, path="pulse_log.json"):
        self.path = path

    def log(self, packet):
        entry = {
            "timestamp": time.time(),
            "packet": packet
        }
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Logging failed: {e}")