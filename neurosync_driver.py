import time
from neurosync_initializer import NeuroSyncCore

class NeuroSyncDriver:
    def __init__(self):
        self.core = NeuroSyncCore()

    def sync_loop(self):
        while True:
            pulse = {
                "sentiment": "neutral",  # placeholder until external hook
                "execution_status": "standby"
            }
            self.core.push_to_memory("current_state", pulse)
            print(f"[NeuroSync] Pulse pushed: {pulse}")
            time.sleep(self.core.sync_rate)