import json
import os

class MemoryManager:
    def __init__(self, filepath="memory/memory.json"):
        self.filepath = filepath
        self.memory = {}
        self.load()

    def load(self):
        """Loads memory from JSON file, or creates a new one if it doesn't exist."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.memory = json.load(f)
            except json.JSONDecodeError:
                self.memory = {}
        else:
            self.memory = {}
            self.save()

    def save(self):
        """Saves the current memory to file."""
        with open(self.filepath, 'w') as f:
            json.dump(self.memory, f, indent=2)

    def remember(self, key, value):
        """Stores a key-value pair in memory."""
        self.memory[key] = value
        self.save()

    def recall(self, key):
        """Retrieves a value by key."""
        return self.memory.get(key, "[I don’t remember anything for that key.]")
