import queue
import threading

class InterfaceHub:
    def __init__(self):
        self.inbound_queue = queue.Queue()
        self.outbound_queue = queue.Queue()
        self.lock = threading.Lock()

    def receive(self, packet):
        with self.lock:
            self.inbound_queue.put(packet)

    def dispatch(self):
        with self.lock:
            if not self.outbound_queue.empty():
                return self.outbound_queue.get()
        return None

    def route_to_outbound(self, data):
        with self.lock:
            self.outbound_queue.put(data)

    def pull_inbound(self):
        with self.lock:
            if not self.inbound_queue.empty():
                return self.inbound_queue.get()
        return None