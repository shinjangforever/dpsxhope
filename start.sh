#!/bin/sh
# เปิดเมนู dpsxhope (macOS, Linux, Termux): bash start.sh
# ใส่คำสั่งต่อท้ายได้ เช่น: bash start.sh status

cd "$(dirname "$0")" || exit 1

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' >/dev/null 2>&1; then
    exec "$candidate" hope.py "$@"
  fi
done

echo "ต้องมี Python 3.11 ขึ้นไป แต่ไม่พบในเครื่องนี้"
echo "ติดตั้งจาก https://www.python.org/downloads/ แล้วรันคำสั่งนี้ใหม่"
exit 1
