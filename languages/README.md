# languages

Code samples และ patterns ในหลายภาษา — แสดง AI engineering patterns ข้ามภาษา

## ภาษาที่รองรับ

| ภาษา | โฟลเดอร์ | จุดเน้น |
|------|---------|---------|
| Go | `go/llm_client.go` | LLM API client (ตรวจ `go vet` และ build ผ่าน ยังไม่ได้รันกับ API จริง) |
| Rust | `rust/tokenizer.rs` | ประมาณจำนวน token และตัด chunk ใช้ std อย่างเดียว คอมไพล์และรันได้ |
| TypeScript | `typescript/client.ts` | LLM client แบบมี type และ structured output (`tsc --strict` ผ่าน รันกับเซิร์ฟเวอร์จำลองได้) |
| Bash | `bash/model_manager.sh` | จัดการโมเดลในเครื่อง: list, pull, bench, health, test |
| SQL | `sql/ai_logs_schema.sql` | schema บันทึก request และติดตามระบบ AI (PostgreSQL ตรวจ syntax แล้ว ไม่ใช่ SQLite หรือ MySQL) |
| YAML | `yaml/ai_stack.docker-compose.yml` | stack สำหรับพัฒนา: Ollama, PostgreSQL, Redis, ai-api (ตรวจ `docker compose config` ผ่าน ยังไม่ได้ขึ้นจริง) |

สถานะการทดสอบล่าสุดของแต่ละชิ้นดูได้จาก `python hope.py list -v`

หลักเลือกว่างานแบบไหนใช้ภาษาอะไร และดูว่าเครื่องของคุณมีเครื่องมือครบหรือยัง อยู่ที่ [แผนที่ stack](../stack/README.md) (`python hope.py stack`)

## แนวคิด

แต่ละไฟล์เป็นต้นแบบของงานที่ใช้บ่อยในภาษานั้น ไม่ได้เป็นชุดเดียวกันข้ามภาษา
ปรับค่าและเงื่อนไขให้ตรงงานของคุณก่อนใช้จริง

## เทคโนโลยี

Go · Rust · TypeScript · Bash · SQL · YAML
