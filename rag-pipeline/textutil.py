"""textutil.py — ตัวช่วยข้อความที่ ingest และ retrieve ใช้ร่วมกัน

สองหน้าที่:
  - clean_extracted_text: ซ่อมข้อความที่ดึงจาก PDF ภาษาไทย (อักขระ NUL, สระอำที่ถูกแยก, ช่องว่างแทรก)
  - tokenize: แยกคำสำหรับ BM25 โดยตัดวรรณยุกต์และการันต์ออก เพื่อให้ข้อความที่สูญเสียเครื่องหมายเหล่านี้
    ตอนดึงจาก PDF ยังค้นเจอด้วยคำถามที่พิมพ์ครบ
"""
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+|[฀-๿]+")
_THAI_RE = re.compile(r"[฀-๿]")
THAI_NGRAM = 3

# ไม้เอก โท ตรี จัตวา และการันต์ (U+0E48-U+0E4C)
_TONE_AND_SILENT = re.compile("[่-์]")
# ตัวควบคุมและตัวกว้างศูนย์ที่ PDF บางตัวใส่มาแทนอักขระที่ map ไม่ได้
_JUNK = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f​-‍﻿]")
# ช่องว่างที่แทรกก่อนสระบน/ล่างหรือวรรณยุกต์ เช่น "ร ้อน"
_SPACE_BEFORE_MARK = re.compile("(?<=[฀-๿]) (?=[ัิ-ฺ็-๎])")


def clean_extracted_text(text: str) -> str:
    """ซ่อมข้อความที่ดึงจาก PDF: ลบอักขระควบคุม, รวมนิคหิต+สระอาเป็นสระอำ, ลบช่องว่างที่แทรกก่อนเครื่องหมาย

    ข้อจำกัด: ถ้า PDF ทำให้วรรณยุกต์หายไปแล้ว (กลายเป็น NUL) จะกู้ตัวอักษรกลับมาไม่ได้
    """
    text = _JUNK.sub("", text)
    text = text.replace("ํา", "ำ")
    return _SPACE_BEFORE_MARK.sub("", text)


def fold(text: str) -> str:
    """รูปแบบสำหรับเทียบข้อความ: ซ่อมข้อความจาก PDF, ตัดวรรณยุกต์และการันต์, ทำเป็นตัวพิมพ์เล็ก

    ใช้ทั้งในการแยกคำและในการเทียบ keyword ตอนประเมิน เพื่อให้ข้อความจาก PDF ที่สูญเสียเครื่องหมาย
    เทียบกับ keyword ที่พิมพ์ครบได้
    """
    return _TONE_AND_SILENT.sub("", clean_extracted_text(text)).lower()


def tokenize(text: str) -> list[str]:
    """แยกคำละตินด้วยตัวคั่น และแยกข้อความไทยเป็น n-gram เพราะภาษาไทยไม่มีช่องว่างระหว่างคำ

    ตัดวรรณยุกต์และการันต์ก่อนแยก (ดู fold) จึงต้องรัน ingest ใหม่กับ index ที่สร้างไว้ก่อนหน้า
    """
    text = fold(text)
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        if _THAI_RE.match(token) and len(token) > THAI_NGRAM:
            tokens.extend(token[i:i + THAI_NGRAM] for i in range(len(token) - THAI_NGRAM + 1))
        else:
            tokens.append(token)
    return tokens
