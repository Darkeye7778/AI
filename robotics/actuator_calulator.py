import time

class ActuatorController:
    def __init__(self):
        self.connected = False

    def connect(self):
        """Simulate connecting to actuators."""
        print("[Actuators] Connecting to motors/servos...")
        self.connected = True

    def move_arm(self, direction: str):
        if not self.connected:
            print("[Actuators] Not connected. Call connect() first.")
            return
        print(f"[Actuators] Moving arm {direction}...")
        time.sleep(0.5)

    def nod_head(self):
        if not self.connected:
            print("[Actuators] Not connected. Call connect() first.")
            return
        print("[Actuators] Nodding head...")
        time.sleep(0.3)
        print("[Actuators] Back to center.")

    def disconnect(self):
        print("[Actuators] Disconnecting.")
        self.connected = False

if __name__ == "__main__":
    bot = ActuatorController()
    bot.connect()
    bot.move_arm("left")
    bot.nod_head()
    bot.disconnect()