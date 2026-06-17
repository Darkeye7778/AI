from main_assistant import model, memory
import os

# Set this to True to enable voice feedback
USE_TTS = False
if USE_TTS :
    from voice.tts import TextToSpeech

def run_cli():
    print("🤖 Assistant CLI is running. Type 'quit' to exit.")
    tts = TextToSpeech() if USE_TTS else None

    while True:
        try:
            user_input = input("You: ")

            if user_input.lower() in ["quit", "exit"]:
                print("Exiting...")
                break

            if user_input.startswith("remember "):
                _, keyval = user_input.split(" ", 1)
                key, val = keyval.split("=", 1)
                memory.remember(key.strip(), val.strip())
                print(f"Assistant: Got it. Remembered {key.strip()}.")
                continue

            if user_input.startswith("recall "):
                key = user_input.split(" ", 1)[1].strip()
                val = memory.recall(key)
                print(f"Assistant: You asked me to remember '{key}': {val}")
                if tts: tts.speak(val)
                continue

            # Route to model
            response = model.route(user_input)
            print(f"Assistant: {response}")

            if tts:
                tts.speak(response)

        except Exception as e:
            print(f"[CLI Error] {e}")

if __name__ == "__main__":
    run_cli()