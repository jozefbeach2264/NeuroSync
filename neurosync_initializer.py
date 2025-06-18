import json
import os

class NeuroSyncCore:
    def __init__(self):
        self.memory_path = "logs/neuro_memory.json"
        self.sync_rate = 60  # seconds
        self.sync_channels = ["market_sentiment", "execution_pulse"]
        self.ensure_memory_file()

    def ensure_memory_file(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, "w") as f:
                json.dump({}, f)

    def push_to_memory(self, key, value):
        with open(self.memory_path, "r") as f:
            data = json.load(f)
        data[key] = value
        with open(self.memory_path, "w") as f:
            json.dump(data, f, indent=4)

    def retrieve_memory(self, key):
        with open(self.memory_path, "r") as f:
            data = json.load(f)
        return data.get(key, None)