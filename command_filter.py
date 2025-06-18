class CommandFilter:
    def __init__(self):
        self.origin_whitelist = ["telegram", "system", "internal"]
        self.throttle_timers = {}
        self.cooldown = 3  # seconds

    def validate(self, command, origin):
        if origin not in self.origin_whitelist:
            return False, "Unauthorized origin"

        now = time.time()
        last = self.throttle_timers.get(origin, 0)
        if now - last < self.cooldown:
            return False, "Command throttled"
        
        self.throttle_timers[origin] = now
        return True, "Command accepted"