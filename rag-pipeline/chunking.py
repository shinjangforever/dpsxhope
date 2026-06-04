"""
chunking.py — แบ่ง document เป็น chunk แบบ semantic / heading-aware

contract ของ chunk dict (ใช้ร่วมกันทุก module):
    chunk = {"id": int, "source": str, "heading": str, "text": str}

โมดูลนี้คืน chunk โดยยังไม่ใส่ "id" (ingest.py รันเลข id ให้ทีหลัง)
ใส่มาแค่ "source", "heading", "text"
"""
import re

import config


def _sliding_window(text: str, size: int, overlap: int) -> list[str]:
    """
    ตัดข้อความเป็นชิ้นด้วย sliding window
    - size    = ความยาวเป้าหมายของแต่ละชิ้น (ตัวอักษร)
    - overlap = จำนวนตัวอักษรที่ซ้อนกับชิ้นก่อนหน้า กันบริบทขาดตรงรอยต่อ
    """
    # ป้องกัน config ผิด: step ต้องเป็นบวก ไม่งั้น loop ไม่จบ
    step = size - overlap
    if step <= 0:
        step = size

    # ข้อความสั้นกว่า size → คืนทั้งก้อน
    if len(text) <= size:
        return [text]

    pieces = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        pieces.append(text[start:end])
        if end >= len(text):   # ถึงท้ายแล้วหยุด กัน window ซ้ำ
            break
        start += step
    return pieces


def _split_sections(text: str) -> list[tuple[str, str]]:
    """
    แบ่งข้อความตามหัวข้อ markdown (#, ##, ###) คืน list ของ (heading, body)
    - heading = ข้อความหัวข้อ (ตัด # และช่องว่างหน้าออกแล้ว); "" สำหรับเนื้อหาก่อนหัวข้อแรก
    - body    = เนื้อหาใต้หัวข้อนั้น จนกว่าจะเจอหัวข้อถัดไป
    """
    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    sections = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        m = heading_re.match(line)
        if m:
            # เจอหัวข้อใหม่ → ปิด section เดิมก่อน
            if current_lines or current_heading:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # flush section สุดท้าย
    if current_lines or current_heading:
        sections.append((current_heading, "\n".join(current_lines)))

    return sections


def chunk_document(text: str, source: str) -> list[dict]:
    """
    แปลง document หนึ่งไฟล์เป็น list ของ chunk dict (มีแค่ source/heading/text)

    กลยุทธ์:
      - RESPECT_HEADINGS = True : แบ่งตามหัวข้อ markdown ก่อน → section ที่ยาวเกิน
        CHUNK_SIZE ค่อยซอยด้วย sliding window (chunk ย่อยพก heading ของ section นั้น)
      - ไม่มีหัวข้อ / RESPECT_HEADINGS = False : sliding window ล้วน heading=""
      - ข้าม chunk ว่าง/มีแต่ whitespace
    """
    size = config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP

    chunks: list[dict] = []

    # เตรียมหน่วยตั้งต้นเป็น list ของ (heading, body)
    if config.RESPECT_HEADINGS:
        units = _split_sections(text)
    else:
        units = [("", text)]

    # วนแต่ละ section → ตัดเป็น chunk ย่อยตามขนาด
    for heading, body in units:
        for piece in _sliding_window(body, size, overlap):
            if not piece.strip():   # ข้าม chunk ว่าง
                continue
            chunks.append({
                "source": source,
                "heading": heading,
                "text": piece,
            })

    return chunks
