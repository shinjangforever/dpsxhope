"""
generate.py — ขั้น generation ของ RAG pipeline
รับ query + chunks ที่ retrieve มาแล้ว → สร้างคำตอบด้วย Claude โดยอ้างอิงหมายเลข [n]

รัน: python generate.py "อธิบาย RAG ให้หน่อย"
"""
import sys

import anthropic
from dotenv import load_dotenv

import config
from retrieve import retrieve

# โหลด .env เพื่อให้ ANTHROPIC_API_KEY เข้ามาใน environment
load_dotenv()

# system prompt: บังคับให้ตอบจาก context เท่านั้น + อ้างอิงหมายเลข [n] เสมอ
SYSTEM_PROMPT = (
    "คุณคือผู้ช่วยตอบคำถามจากเอกสารที่ให้มาเท่านั้น (context-grounded assistant)\n"
    "กติกาที่ต้องทำตามอย่างเคร่งครัด:\n"
    "1. ตอบโดยใช้ 'เฉพาะ' ข้อมูลใน context ที่ให้เท่านั้น ห้ามเดา ห้ามมั่ว "
    "ห้ามดึงความรู้นอก context\n"
    "2. ถ้า context ไม่มีข้อมูลพอจะตอบ ให้บอกตรงๆ ว่า 'ไม่พบข้อมูลใน context ที่ให้มา'\n"
    "3. ทุกข้อความที่ดึงมาจาก context ต้องอ้างอิงหมายเลขแหล่งที่มาแบบ [n] "
    "(เช่น [1], [2]) ตรงท้ายประโยคที่เกี่ยวข้อง\n"
    "4. ถ้าหนึ่งประโยคอ้างหลายแหล่ง ให้ใส่ต่อกันได้ เช่น [1][3]"
)


def format_context(chunks: list[dict]) -> str:
    """
    สร้างสตริง context พร้อมหมายเลขอ้างอิง เพื่อให้ LLM อ้าง [1][2] ได้
    รูปแบบต่อ chunk:
        [n] (source: <source>, heading: <heading>)
        <text>
    คั่นแต่ละ chunk ด้วยบรรทัดว่าง
    """
    blocks = []
    for i, c in enumerate(chunks, 1):
        # heading อาจเป็น "" ได้ตาม contract — แสดงตามจริง
        header = f"[{i}] (source: {c.get('source', '')}, heading: {c.get('heading', '')})"
        blocks.append(f"{header}\n{c.get('text', '')}")
    return "\n\n".join(blocks)


def generate(query: str, chunks: list[dict]) -> str:
    """
    เรียก Claude สร้างคำตอบจาก query + chunks
    - ใช้ CLAUDE_MODEL, MAX_TOKENS จาก config
    - เปิด prompt caching ที่ system prompt ถ้า USE_PROMPT_CACHING=True (node 09)
    - คืน text คำตอบ
    """
    context = format_context(chunks)

    # system prompt: ถ้าเปิด caching ใช้ list-form + cache_control ephemeral
    # (cache ตัว system prompt ข้าม request → ลด cost/latency)
    if config.USE_PROMPT_CACHING:
        system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system = SYSTEM_PROMPT

    # api key มาจาก config.api_key() (error ชัดถ้าไม่ตั้ง)
    client = anthropic.Anthropic(api_key=config.api_key())
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nคำถาม: {query}",
            }
        ],
    )
    # รวม text จากทุก block (กันกรณี content มีหลายชิ้น)
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


if __name__ == "__main__":
    # รับ query จาก argv → retrieve → generate → print
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "เอกสารนี้เกี่ยวกับอะไร?"
    print(f"\n🔍 query: {q}\n")

    chunks = retrieve(q)
    print(f"retrieved {len(chunks)} chunks\n")

    answer = generate(q, chunks)
    print(f"📝 answer:\n{answer}\n")
