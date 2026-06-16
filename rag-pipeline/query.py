"""
query.py — รับคำถาม → hybrid retrieve → generate answer ด้วย Claude
รัน: python query.py "อธิบาย RAG ให้หน่อย"
     python query.py  (ไม่ใส่ argument จะใช้ default query)
"""
import sys

from dotenv import load_dotenv

import config
from retrieve import retrieve
from generate import generate

load_dotenv()


def main(query: str) -> None:
    print(f"\n🔍 query: {query}\n")

    chunks = retrieve(query, top_k=config.TOP_K)
    print(f"retrieved {len(chunks)} chunks:")
    for i, c in enumerate(chunks, 1):
        preview = c["text"][:80].replace("\n", " ")
        print(f"  [{i}] score={c['score']:.4f} | {c.get('source', '')} | {preview}...")

    print("\n⚙️  generating answer...\n")
    answer = generate(query, chunks)
    print(f"📝 answer:\n{answer}\n")


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is RAG and how does it work?"
    main(q)
