"""
pipeline.py — CLI orchestrator รวมทุกขั้นของ RAG pipeline ไว้ที่เดียว
flow: ingest → retrieve → generate → eval

ใช้ argparse subcommands 3 คำสั่ง:

  1) ingest  — โหลดเอกสาร + สร้าง index
       python pipeline.py ingest --docs sample_docs/

  2) query   — ถาม 1 คำถาม: retrieve + generate (โชว์ chunks ที่ดึง + score แล้วตามด้วยคำตอบ)
       python pipeline.py query "RAG คืออะไร?"

  3) eval    — รันชุดประเมินคุณภาพ (recall@k, context_precision, faithfulness)
       python pipeline.py eval
"""
import argparse

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


def cmd_query(args: argparse.Namespace) -> None:
    """retrieve + generate: โชว์ chunks ที่ดึง (พร้อม score) แล้วตามด้วยคำตอบ"""
    from retrieve import retrieve
    from generate import generate

    query = args.text
    print(f"\n🔍 query: {query}\n")

    chunks = retrieve(query)
    print(f"retrieved {len(chunks)} chunks:")
    for i, c in enumerate(chunks, 1):
        # โชว์เลขอ้างอิง + score + source/heading + ตัวอย่างข้อความ
        snippet = c["text"][:80].replace("\n", " ")
        print(
            f"  [{i}] score={c['score']:.3f} | "
            f"{c['source']} | {c.get('heading', '')} | {snippet}..."
        )

    print("\n⚙️  generating answer...\n")
    answer = generate(query, chunks)
    print(f"📝 answer:\n{answer}\n")


def cmd_eval(args: argparse.Namespace) -> None:
    """รันชุดประเมิน (delegate ไป evaluate.run_eval)"""
    import evaluate

    evaluate.run_eval()


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
        "--docs", default="sample_docs/", help="โฟลเดอร์ที่เก็บไฟล์เอกสาร (.txt)"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    # query
    p_query = sub.add_parser("query", help="ถาม 1 คำถาม: retrieve + generate")
    p_query.add_argument("text", help="ข้อความคำถาม")
    p_query.set_defaults(func=cmd_query)

    # eval
    p_eval = sub.add_parser("eval", help="รันชุดประเมินคุณภาพ")
    p_eval.set_defaults(func=cmd_eval)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
