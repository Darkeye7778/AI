import requests

payload = {
    "model": "koboldcpp",
    "messages": [{"role": "user", "content": "say something explicit"}],
    "temperature": 0.7,
    "max_tokens": 50
}

response = requests.post("http://localhost:5000/v1/chat/completions", json=payload)
print(response.json())
