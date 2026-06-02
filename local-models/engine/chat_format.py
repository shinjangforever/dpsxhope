"""
chat_format.py — Prompt template ตามแต่ละโมเดล
แต่ละโมเดลมี chat format ต่างกัน — ใส่ผิดทำให้คุณภาพ output ลดฮวบ

Format families:
  ChatML       → Qwen, Phi, OpenHermes, Mistral-Instruct (บางรุ่น)
  Llama3       → Meta Llama 3.x ทุกรุ่น
  Llama2       → Meta Llama 2, CodeLlama
  Gemma        → Google Gemma 2
  DeepSeek     → DeepSeek-R1, DeepSeek-V2
  Alpaca       → WizardLM, Vicuna เก่า
  Raw          → base model (ไม่มี instruction tuning)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FormatFamily(str, Enum):
    CHATML   = "chatml"
    LLAMA3   = "llama3"
    LLAMA2   = "llama2"
    GEMMA    = "gemma"
    DEEPSEEK = "deepseek"
    ALPACA   = "alpaca"
    RAW      = "raw"


@dataclass
class ChatMessage:
    role: str    # system | user | assistant
    content: str


# ── Model → Format mapping ────────────────────────────────────

MODEL_FORMAT_MAP: dict[str, FormatFamily] = {
    # Llama 3.x
    "llama3":           FormatFamily.LLAMA3,
    "llama3.1":         FormatFamily.LLAMA3,
    "llama3.2":         FormatFamily.LLAMA3,
    "llama3.3":         FormatFamily.LLAMA3,
    "llama-3":          FormatFamily.LLAMA3,
    # Llama 2
    "llama2":           FormatFamily.LLAMA2,
    "codellama":        FormatFamily.LLAMA2,
    # Mistral / Mixtral (ChatML-based instruct)
    "mistral":          FormatFamily.CHATML,
    "mixtral":          FormatFamily.CHATML,
    "mistral-nemo":     FormatFamily.CHATML,
    # Qwen
    "qwen2":            FormatFamily.CHATML,
    "qwen2.5":          FormatFamily.CHATML,
    # Phi
    "phi3":             FormatFamily.CHATML,
    "phi3.5":           FormatFamily.CHATML,
    # Gemma
    "gemma2":           FormatFamily.GEMMA,
    "gemma":            FormatFamily.GEMMA,
    # DeepSeek
    "deepseek-r1":      FormatFamily.DEEPSEEK,
    "deepseek-v2":      FormatFamily.DEEPSEEK,
    "deepseek-coder":   FormatFamily.DEEPSEEK,
    # Alpaca variants
    "wizardlm":         FormatFamily.ALPACA,
    "vicuna":           FormatFamily.ALPACA,
    "openchat":         FormatFamily.CHATML,
    "openhermes":       FormatFamily.CHATML,
    "neural-chat":      FormatFamily.CHATML,
}


def detect_format(model_name: str) -> FormatFamily:
    """ตรวจจาก model name (case-insensitive, prefix match)"""
    name = model_name.lower().split(":")[0]   # ตัด :tag ออก
    for key, fmt in MODEL_FORMAT_MAP.items():
        if name.startswith(key) or key in name:
            return fmt
    return FormatFamily.CHATML   # default ที่ปลอดภัยที่สุด


# ── Format functions ──────────────────────────────────────────

def format_chatml(messages: list[ChatMessage]) -> str:
    """
    ChatML format (Qwen, Phi, Mistral-instruct, OpenHermes)
    <|im_start|>role\ncontent<|im_end|>
    """
    parts = []
    for m in messages:
        parts.append(f"<|im_start|>{m.role}\n{m.content}<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


def format_llama3(messages: list[ChatMessage]) -> str:
    """
    Llama 3 format
    <|begin_of_text|><|start_header_id|>role<|end_header_id|>\ncontent<|eot_id|>
    """
    parts = ["<|begin_of_text|>"]
    for m in messages:
        parts.append(
            f"<|start_header_id|>{m.role}<|end_header_id|>\n\n"
            f"{m.content}<|eot_id|>"
        )
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(parts)


def format_llama2(messages: list[ChatMessage]) -> str:
    """
    Llama 2 format
    [INST] <<SYS>>\nsystem\n<</SYS>>\n\nuser [/INST]
    """
    system = next((m.content for m in messages if m.role == "system"), "")
    turns = [m for m in messages if m.role != "system"]
    parts = []
    for i, m in enumerate(turns):
        if m.role == "user":
            sys_block = f"<<SYS>>\n{system}\n<</SYS>>\n\n" if i == 0 and system else ""
            parts.append(f"[INST] {sys_block}{m.content} [/INST]")
        elif m.role == "assistant":
            parts.append(f" {m.content} </s><s>")
    return "".join(parts)


def format_gemma(messages: list[ChatMessage]) -> str:
    """
    Gemma 2 format
    <start_of_turn>role\ncontent<end_of_turn>
    """
    parts = []
    for m in messages:
        role = "user" if m.role in ("user", "system") else "model"
        parts.append(f"<start_of_turn>{role}\n{m.content}<end_of_turn>")
    parts.append("<start_of_turn>model\n")
    return "\n".join(parts)


def format_deepseek(messages: list[ChatMessage]) -> str:
    """
    DeepSeek format (R1 ใช้ thinking tokens)
    <｜begin▁of▁sentence｜>system\nUser: ...\nAssistant: <think>
    """
    system = next((m.content for m in messages if m.role == "system"), "")
    parts = [f"<｜begin▁of▁sentence｜>{system}"]
    for m in messages:
        if m.role == "user":
            parts.append(f"User: {m.content}")
        elif m.role == "assistant":
            parts.append(f"Assistant: {m.content}<｜end▁of▁sentence｜>")
    parts.append("Assistant: <think>")
    return "\n".join(parts)


def format_alpaca(messages: list[ChatMessage]) -> str:
    """
    Alpaca format (WizardLM, Vicuna)
    ### Instruction:\n...\n### Response:
    """
    system = next((m.content for m in messages if m.role == "system"), "")
    user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    header = f"{system}\n\n" if system else ""
    return f"{header}### Instruction:\n{user}\n\n### Response:\n"


# ── Public API ────────────────────────────────────────────────

_FORMATTERS = {
    FormatFamily.CHATML:   format_chatml,
    FormatFamily.LLAMA3:   format_llama3,
    FormatFamily.LLAMA2:   format_llama2,
    FormatFamily.GEMMA:    format_gemma,
    FormatFamily.DEEPSEEK: format_deepseek,
    FormatFamily.ALPACA:   format_alpaca,
    FormatFamily.RAW:      lambda msgs: msgs[-1].content if msgs else "",
}


def build_prompt(
    model_name: str,
    user: str,
    system: str = "You are a helpful assistant.",
    history: Optional[list[ChatMessage]] = None,
) -> tuple[str, FormatFamily]:
    """สร้าง prompt string ที่ถูกต้องสำหรับโมเดลที่ระบุ"""
    fmt = detect_format(model_name)
    messages = []
    if system:
        messages.append(ChatMessage("system", system))
    if history:
        messages.extend(history)
    messages.append(ChatMessage("user", user))
    prompt = _FORMATTERS[fmt](messages)
    return prompt, fmt


# ── Demo ─────────────────────────────────────────────────────

if __name__ == "__main__":
    test_models = [
        ("llama3.2", "อธิบาย RAG ให้หน่อย"),
        ("qwen2.5:7b", "Explain embeddings"),
        ("gemma2:9b", "What is an agent?"),
        ("deepseek-r1:8b", "Solve: what is 2+2?"),
        ("mistral", "Write a haiku about AI"),
    ]

    for model, user_msg in test_models:
        prompt, fmt = build_prompt(model, user_msg, system="You are a helpful assistant.")
        print(f"\n{'='*50}")
        print(f"model: {model}  →  format: {fmt}")
        print(f"{'─'*50}")
        print(prompt[:300] + ("..." if len(prompt) > 300 else ""))
