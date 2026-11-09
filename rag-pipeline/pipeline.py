"""
pipeline.py — CLI orchestrator รวมทุกขั้นของ RAG pipeline ไว้ที่เดียว
flow: ingest → retrieve → generate → eval

ใช้ argparse subcommands (ingest, query, chat, eval):

  1) ingest  — โหลดเอกสาร + สร้าง index
       python pipeline.py ingest --docs sample_docs/

  2) query   — ถาม 1 คำถาม: retrieve + generate (โชว์ chunks ที่ดึง + score แล้วตามด้วยคำตอบ)
       python pipeline.py query "RAG คืออะไร?"

  3) eval    — รันชุดประเมินคุณภาพ (recall@k, context_precision, faithfulness)
       python pipeline.py eval
"""
import argparse
import json
import sys

from dotenv import load_dotenv

import config

# โหลด .env ตั้งแต่เริ่ม เพื่อให้ทุก subcommand มี ANTHROPIC_API_KEY พร้อมใช้
load_dotenv()


def cmd_ingest(args: argparse.Namespace) -> None:
    """โหลดเอกสารจากโฟลเดอร์ → สร้าง index (เรียก ingest module)"""
    import ingest

    docs = ingest.load_docs(args.docs)
    print(f"loaded {len(docs)} documents จาก {args.docs}")
    ingest.build_index(docs)


def ask(query: str, top_k: int = config.TOP_K) -> dict:
    """API หลักสำหรับนำไปเรียกจากแอปอื่น คืนคำตอบพร้อมแหล่งอ้างอิง"""
    from retrieve import retrieve
    from generate import generate

    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        raise SystemExit("ยังไม่มี index ให้รัน: python pipeline.py ingest --docs <โฟลเดอร์เอกสาร>")

    return {"query": query, "answer": generate(query, chunks), "sources": _sources(chunks)}


def _sources(chunks: list) -> list[dict]:
    return [
        {
            "ref": i,
            "source": c.get("source", ""),
            "heading": c.get("heading", ""),
            "score": round(float(c.get("score", 0)), 4),
            "text": c.get("text", ""),
        }
        for i, c in enumerate(chunks, 1)
    ]


def search_only(query: str, top_k: int = config.TOP_K) -> dict:
    """ค้นช่วงเอกสารที่เกี่ยวข้องอย่างเดียว ไม่เรียก AI (ใช้ได้โดยไม่ต้องมี key หรือ Ollama)"""
    from retrieve import retrieve

    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        raise SystemExit("ยังไม่มี index ให้รัน: python pipeline.py ingest --docs <โฟลเดอร์เอกสาร>")
    best = " ".join(chunks[0]["text"].split())
    return {
        "query": query,
        "answer": f"(โหมดค้นหาอย่างเดียว ไม่เรียก AI) ช่วงเอกสารที่เกี่ยวข้องที่สุด: {best[:300]}",
        "sources": _sources(chunks),
    }


def cmd_query(args: argparse.Namespace) -> None:
    """ถามหนึ่งคำถาม แล้วแสดงแบบอ่านง่ายหรือ JSON"""
    result = ask(args.text, top_k=args.top_k)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print_result(result)


def print_result(result: dict) -> None:
    """แสดงคำตอบ ตามด้วยแหล่งอ้างอิง (ชื่อไฟล์และหัวข้อ)"""
    print(f"\n📝 คำตอบ:\n{result['answer']}\n")
    print("แหล่งอ้างอิง:")
    for item in result["sources"]:
        name = item["source"].replace("\\", "/").rsplit("/", 1)[-1]
        heading = f" — {item['heading']}" if item["heading"] else ""
        print(f"  [{item['ref']}] {name}{heading}  (คะแนน {item['score']:.3f})")


def cmd_chat(args: argparse.Namespace) -> None:
    """ถามต่อเนื่องหลายข้อ โหลดโมเดลครั้งเดียว เว้นว่างหรือพิมพ์ exit เพื่อออก"""
    interactive = sys.stdin.isatty()
    answer = search_only if args.search_only else ask
    if interactive:
        print("พิมพ์คำถามแล้วกด Enter (เว้นว่างหรือพิมพ์ exit เพื่อออก)")
    while True:
        try:
            text = input("\nคำถาม> " if interactive else "").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text or text.lower() in {"exit", "quit", "q"}:
            break
        if not interactive:
            print(f"\nคำถาม> {text}")  # ป้อนคำถามจากไฟล์/โปรแกรมอื่น จึงต้องแสดงเองให้อ่านรู้เรื่อง
        try:
            print_result(answer(text, top_k=args.top_k))
        except SystemExit as exc:
            print(exc)
            break
        except Exception as exc:
            print(f"ตอบไม่ได้: {exc}")


def cmd_eval(args: argparse.Namespace) -> None:
    """รันชุดประเมิน (delegate ไป evaluate.run_eval)"""
    import evaluate

    passed = evaluate.run_eval(args.cases, min_recall=args.min_recall, use_judge=not args.no_judge)
    if not passed:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    """ประกอบ argparse parser พร้อม subcommands ทั้ง 3"""
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="RAG pipeline CLI — ingest / query / eval",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="โหลดเอกสาร + สร้าง index")
    p_ingest.add_argument(
        "--docs", default="sample_docs/", help="โฟลเดอร์ที่เก็บ .txt, .md หรือ .pdf"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    # query
    p_query = sub.add_parser("query", help="ถาม 1 คำถาม: retrieve + generate")
    p_query.add_argument("text", help="ข้อความคำถาม")
    p_query.add_argument("--top-k", type=int, default=config.TOP_K, help="จำนวนแหล่งอ้างอิง")
    p_query.add_argument("--json", action="store_true", help="แสดงผลเป็น JSON")
    p_query.set_defaults(func=cmd_query)

    # chat
    p_chat = sub.add_parser("chat", help="ถามต่อเนื่องหลายข้อ")
    p_chat.add_argument("--top-k", type=int, default=config.TOP_K, help="จำนวนแหล่งอ้างอิง")
    p_chat.add_argument("--search-only", action="store_true", help="แสดงเฉพาะช่วงเอกสารที่ค้นเจอ ไม่เรียก AI")
    p_chat.set_defaults(func=cmd_chat)

    # eval
    p_eval = sub.add_parser("eval", help="รันชุดประเมินคุณภาพ")
    p_eval.add_argument("--cases", default="eval_cases.json", help="ไฟล์ชุดทดสอบ JSON")
    p_eval.add_argument("--min-recall", type=float, default=0.0, help="คืน exit code 1 ถ้า recall ต่ำกว่าค่านี้")
    p_eval.add_argument("--no-judge", action="store_true", help="ไม่เรียก LLM ตรวจ faithfulness")
    p_eval.set_defaults(func=cmd_eval)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
