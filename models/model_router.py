import subprocess
import requests
from llama_cpp import Llama

class ModelRouter:
    def __init__(self):
        self.mode = "safe"
        self.model = Llama(model_path="models\mistral-7b-instruct-v0.1.Q6_K.gguf", n_ctx=2048)

        # NSFW model served via KoboldCPP in OpenAI-compatible mode
        self.nsfw_api_url = "http://localhost:5000/v1/chat/completions"

    def route(self, prompt: str, mode: str = "safe") -> str:
        print(f"[DEBUG] Routing to mode: {mode}")

        if mode == "safe":
            formatted_prompt = f"[INST] {prompt.strip()} [/INST]"
            output = self.model(formatted_prompt, max_tokens=512, stop=["</s>"])
            return output["choices"][0]["text"].strip()
        elif mode == "nsfw":
            return self.query_nsfw_model(prompt)
        elif mode == "robot":
            return self.query_robot_model(prompt)
        else:
            return f"[ModelRouter] Unknown mode '{mode}' requested."

    def query_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.default_model,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.ollama_url, json=payload)
            if response.status_code == 200:
                return response.json().get("response", "[No response from model]")
            else:
                return f"[Ollama Error] Status {response.status_code}: {response.text}"
        except Exception as e:
            return f"[Ollama Connection Error] {e}"

    def query_nsfw_model(self, prompt: str) -> str:
        payload = {
            "model": "koboldcpp",  # Optional depending on server
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        try:
            response = requests.post(self.nsfw_api_url, json=payload)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"[NSFW Model Error] Status {response.status_code}: {response.text}"
        except Exception as e:
            return f"[NSFW Model Connection Error] {e}"

    def query_robot_model(self, prompt: str) -> str:
        return "[Robot model not yet implemented.]"
