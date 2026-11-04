"""textutil.py — tokenizer ที่ ingest และ retrieve ใช้ร่วมกัน"""
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u0E00-\u0E7F]+")
_THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
THAI_NGRAM = 3


def tokenize(text: str) -> list[str]:
    """แยกคำละตินด้วยตัวคั่น และแยกข้อความไทยเป็น n-gram เพราะภาษาไทยไม่มีช่องว่างระหว่างคำ"""
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text.lower()):
        if _THAI_RE.match(token) and len(token) > THAI_NGRAM:
            tokens.extend(token[i:i + THAI_NGRAM] for i in range(len(token) - THAI_NGRAM + 1))
        else:
            tokens.append(token)
    return tokens
