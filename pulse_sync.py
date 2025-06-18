import time
import threading
from interface_hub import InterfaceHub

class PulseSync:
    def __init__(self, interval=1):
        self.interval = interval
        self.hub = InterfaceHub()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()

    def loop(self):
        while self.running:
            self.transmit()
            time.sleep(self.interval)

    def transmit(self):
        payload = self.hub.pull_inbound()
        if payload:
            # Simulated broadcast
            print(f"[PULSE OUT] {payload}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()