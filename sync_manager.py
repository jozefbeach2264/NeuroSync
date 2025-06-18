import time
import hashlib
import json
import os

class SyncManager:
    def __init__(self, buffer_path="buffer/last_known_state.json", log_path="logs/sync_status.log"):
        self.buffer_path = buffer_path
        self.log_path = log_path
        self.last_snapshot = {}
        self._load_snapshot()

    def _load_snapshot(self):
        if os.path.exists(self.buffer_path):
            with open(self.buffer_path, "r") as f:
                try:
                    self.last_snapshot = json.load(f)
                except json.JSONDecodeError:
                    self.last_snapshot = {}

    def validate_sync(self, current_state):
        last_hash = self._hash_dict(self.last_snapshot)
        curr_hash = self._hash_dict(current_state)
        if last_hash != curr_hash:
            self._log_sync(current_state, "STATE MISMATCH")
            return False
        return True

    def _hash_dict(self, d):
        return hashlib.md5(json.dumps(d, sort_keys=True).encode()).hexdigest()

    def _log_sync(self, state, note):
        log_line = {
            "timestamp": time.time(),
            "note": note,
            "checksum": self._hash_dict(state)
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(log_line) + "\n")

    def save_state(self, state):
        with open(self.buffer_path, "w") as f:
            json.dump(state, f, indent=2)
        self.last_snapshot = state