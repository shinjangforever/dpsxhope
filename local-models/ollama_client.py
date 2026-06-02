"""
ollama_client.py — ใช้ local LLM ผ่าน Ollama (รันบนเครื่องตัวเอง ไม่ต้อง API key)
ต้องติดตั้ง Ollama ก่อน: https://ollama.com

คำสั่งเริ่มต้น:
  ollama serve                    # เปิด server
  ollama pull llama3.2            # ดาวน์โหลดโมเดล
  python ollama_client.py "ถามอะไรก็ได้"
"""
import json
import sys
import urllib.request
from typing import Iterator

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"   # เปลี่ยนได้: mistral, gemma2, qwen2.5, phi3, deepseek-r1


def chat(prompt: str, model: str = DEFAULT_MODEL, stream: bool = False) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req) as resp:
        if not stream:
            data = json.load(resp)
            return data["message"]["content"]

        # streaming
        full = ""
        for line in resp:
            if not line.strip():
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            print(token, end="", flush=True)
            full += token
            if chunk.get("done"):
                break
        print()
        return full


def list_models() -> list[str]:
    req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return [m["name"] for m in data.get("models", [])]


def embed(text: str, model: str = "nomic-embed-text") -> list[float]:
    """สร้าง embedding ด้วย local model (ใช้แทน sentence-transformers ได้)"""
    payload = json.dumps({"model": model, "input": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data["embeddings"][0]


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "สวัสดี บอกชื่อตัวเองหน่อย"

    print(f"model: {DEFAULT_MODEL}")
    print(f"prompt: {prompt}\n---")
    reply = chat(prompt, stream=True)
