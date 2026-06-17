from models.model_router import ModelRouter
from memory.memory_handler import MemoryManager
from images.gen_image import ImageGenerator

# Step 1: Load memory (this holds user preferences, reminders, identity)
memory = MemoryManager("memory/memory.json")

# Step 2: Initialize the model router (to direct prompts to right LLM)
model = ModelRouter()
image_generator = ImageGenerator()

# Step 3: Optional TTS module
USE_TTS = False
if USE_TTS :
    from voice.tts import TextToSpeech
    text_to_speech = TextToSpeech()
else :
    text_to_speech = None

print("🤖 Your Assistant is now running! Type 'quit' to exit.")

# Step 4: Command loop — this is your CLI interface for now
while True:
    user_input = input("You: ")
    if user_input.lower() in ["quit", "exit"]:
        print("Exiting...")
        break

    # Optional: Check for memory queries
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
        if text_to_speech:
            text_to_speech.speak(val)
        continue

    IMAGE_KEYWORDS = ["draw", "generate image", "picture of", "image of", "generate"]
    if any(k in user_input.lower() for k in IMAGE_KEYWORDS):
        prompt = user_input.replace("generate image of", "").replace("draw", "").strip()
        image_path = image_generator.generate_image(prompt)
        if image_path:
            print(f"Assistant: Image generated at {image_path}")
        else:
            print("Assistant: Failed to generate image.")
        continue

    # Step 5: Route prompt to model
    NSFW_KEYWORDS = ["nsfw", "explicit", "lewd", "erotic", "uncensored", "nude"]
    if any(word in user_input.lower() for word in NSFW_KEYWORDS):
        mode = "nsfw"
    else:
        mode = "safe"

    print(f"[DEBUG] Routing to mode: {mode}")

    response = model.route(user_input, mode=mode)
    print(f"Assistant: {response}")

    # Step 6: Optional TTS output
    if text_to_speech:
        text_to_speech.speak(response)

# Save memory before closing
memory.save()