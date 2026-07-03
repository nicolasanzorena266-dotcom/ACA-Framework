class MemoryEngine:
    def __init__(self):
        self.working = {}
        self.episodic = []
        self.semantic = {}
        self.procedural = {}

    def remember_working(self, key, value):
        self.working[key] = value

    def clear_working(self):
        self.working.clear()
