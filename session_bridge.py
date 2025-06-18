class SessionBridge:
    def __init__(self):
        self.last_inbound = None
        self.last_outbound = None

    def sync_inbound(self, data):
        self.last_inbound = data

    def sync_outbound(self):
        if self.last_inbound:
            response = self.process(self.last_inbound)
            self.last_outbound = response
            return response
        return None

    def process(self, data):
        # Echo for now; will be replaced with transform logic
        return {"echo": data}