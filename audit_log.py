import json
import time

class AuditLog:
    def __init__(self, path="logs/audit_log.json"):
        self.path = path

    def log(self, origin, path_trace, result):
        entry = {
            "timestamp": time.time(),
            "origin": origin,
            "route": path_trace,
            "result": result
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")