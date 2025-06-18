import time

class Heartbeat:
    def __init__(self):
        self.last_beat = time.time()

    def pulse(self):
        self.last_beat = time.time()
        print(f"[HEARTBEAT] {self.last_beat}")

    def age(self):
        return time.time() - self.last_beat

    def is_stale(self, threshold=10):
        return self.age() > threshold