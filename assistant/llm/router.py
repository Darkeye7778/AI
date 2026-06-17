"""LLM router — evolved from models/model_router.py with memory-aware prompting."""

from __future__ import annotations

import os
from pathlib import Path

import requests

from assistant.config import settings


class LLMRouter:
    def __init__(self):
        self._local_model = None
        self.nsfw_api_url = settings.nsfw_api_url

    def _load_local(self):
        if self._local_model is None:
            from llama_cpp import Llama
            model_path = str(settings.llm_model_path)
            if not Path(model_path).exists():
                raise FileNotFoundError(
                    f"Model not found: {model_path}\n"
                    f"Keep PersonalAssistant.exe in D:\\AI_Assistant\\ (or whole project folder together)."
                )
            self._local_model = Llama(model_path=model_path, n_ctx=4096)
        return self._local_model

    def generate(
        self,
        prompt: str,
        system: str = "",
        mode: str = "safe",
        max_tokens: int = 1024,
    ) -> str:
        if settings.llm_provider == "openai" and settings.llm_api_key:
            return self._openai_chat(prompt, system, max_tokens)
        if mode == "nsfw":
            return self._nsfw_chat(prompt, system, max_tokens)
        return self._local_chat(prompt, system, max_tokens)

    def _local_chat(self, prompt: str, system: str, max_tokens: int) -> str:
        model = self._load_local()
        full = ""
        if system:
            full += f"[SYSTEM]\n{system}\n[/SYSTEM]\n"
        full += f"[INST] {prompt.strip()} [/INST]"
        output = model(full, max_tokens=max_tokens, stop=["</s>"])
        return output["choices"][0]["text"].strip()

    def _openai_chat(self, prompt: str, system: str, max_tokens: int) -> str:
        import openai
        client = openai.OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def _nsfw_chat(self, prompt: str, system: str, max_tokens: int) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": "koboldcpp",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(self.nsfw_api_url, json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            return f"[NSFW Model Error] {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"[NSFW Model Connection Error] {e}"