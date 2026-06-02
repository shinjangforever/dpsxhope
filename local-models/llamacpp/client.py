"""
client.py — ใช้ llama.cpp server ผ่าน OpenAI-compatible API
ต้องรัน server.sh ก่อน: bash server.sh model.gguf

รัน: python client.py "คำถาม"
"""
import json
import sys
import urllib.request

BASE_URL = "http://localhost:8080"


def chat(prompt: str, system: str = "You are a helpful assistant.", max_tokens: int = 512) -> str:
    payload = json.dumps({
        "model": "local",
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    return data["choices"][0]["message"]["content"]


def stream_chat(prompt: str, system: str = "You are a helpful assistant.") -> str:
    payload = json.dumps({
        "model": "local",
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    full = ""
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
                token = chunk["choices"][0]["delta"].get("content", "")
                print(token, end="", flush=True)
                full += token
            except Exception:
                continue
    print()
    return full


def model_info() -> dict:
    req = urllib.request.Request(f"{BASE_URL}/v1/models")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "สวัสดี บอกชื่อโมเดลของคุณ"
    print(f"prompt: {prompt}\n---")
    stream_chat(prompt)
