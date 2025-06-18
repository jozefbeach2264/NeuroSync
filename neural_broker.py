import json
from interface_hub import InterfaceHub
from session_bridge import SessionBridge

class NeuralBroker:
    def __init__(self, config_path="node_config.json"):
        self.config = self.load_config(config_path)
        self.hub = InterfaceHub()
        self.bridge = SessionBridge()

    def load_config(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def intake(self, signal):
        if isinstance(signal, dict):
            self.hub.receive(signal)
            self.bridge.sync_inbound(signal)

    def emit(self):
        outbound = self.bridge.sync_outbound()
        if outbound:
            self.hub.route_to_outbound(outbound)
            return outbound
        return None