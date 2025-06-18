import time

class ToggleDispatcher:
    def __init__(self):
        self.active_modules = {}
        self.lockouts = {}

    def activate(self, module_name, expires_in=60):
        expiry = time.time() + expires_in
        self.active_modules[module_name] = expiry
        return {"status": "activated", "module": module_name, "expires": expiry}

    def deactivate(self, module_name):
        if module_name in self.active_modules:
            del self.active_modules[module_name]
        return {"status": "deactivated", "module": module_name}

    def is_active(self, module_name):
        expiry = self.active_modules.get(module_name, 0)
        return time.time() < expiry

    def lockout(self, module_name, minutes=2):
        self.lockouts[module_name] = time.time() + (minutes * 60)

    def is_locked(self, module_name):
        return time.time() < self.lockouts.get(module_name, 0)