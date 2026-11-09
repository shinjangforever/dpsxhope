"""เมนูหลักภาษาไทย ให้ใช้งานได้โดยไม่ต้องจำคำสั่ง"""
from . import commands, engine, scaffold, settings
from .commands import Context
from .ui import Cancelled

TITLE = "dpsxhope — คู่มือและต้นแบบ AI ที่ใช้งานได้จริง"
K = commands.MENU_KEYS
MENU = [
    (K["setup"], "ตั้งค่าครั้งแรก (ติดตั้ง และเลือก AI ที่ใช้ตอบ)"),
    (K["demo"], "ลองดูก่อน (เดโม 1-2 นาที ด้วยเอกสารตัวอย่าง)"),
    (K["docs"], "ใส่เอกสารของฉัน"),
    (K["ask"], "ถามคำถามจากเอกสาร"),
    (K["agent"], "ให้ agent ทำงาน (ใช้ Claude)"),
    (K["settings"], "ตั้งค่า (เปลี่ยน AI, ใส่ key, ปรับค่า)"),
    (K["status"], "ตรวจเครื่อง และดูว่าขั้นต่อไปคืออะไร"),
    (K["tool"], "สร้างเครื่องมือใหม่ให้ agent"),
    ("0", "ออก"),
]


def _pause(ctx: Context) -> None:
    try:
        ctx.io.ask("\nกด Enter เพื่อกลับเมนู")
    except Cancelled:
        pass


def docs_menu(ctx: Context) -> int:
    io = ctx.io
    io.say("\nจะใช้เอกสารจากไหน")
    where = io.choose("เลือก", [
        ("mine", "โฟลเดอร์ my-docs ของโปรแกรม (วางไฟล์ไว้ที่นั่น)"),
        ("other", "โฟลเดอร์อื่นในเครื่อง (พิมพ์หรือวางที่อยู่)"),
        ("sample_th", "ลองกับเอกสารตัวอย่างภาษาไทย"),
        ("sample_en", "ลองกับเอกสารตัวอย่างภาษาอังกฤษ"),
    ], default="mine")
    if where == "mine":
        folder = commands.ensure_docs_dir(ctx)
        io.say(f"โฟลเดอร์: {folder}")
        io.say("วางไฟล์ .txt .md .pdf ไว้ในโฟลเดอร์นี้ก่อน")
        if not io.confirm("วางไฟล์เรียบร้อยแล้วใช่ไหม", default=True):
            return 1
        return commands.docs(ctx)
    if where == "other":
        path = io.ask("ที่อยู่โฟลเดอร์ (ลากโฟลเดอร์มาวางในหน้าต่างนี้ได้)")
        return commands.docs(ctx, folder=path) if path else 2
    return commands.docs(ctx, sample=where.split("_")[1])


def settings_menu(ctx: Context) -> int:
    io = ctx.io
    show_all = False
    while True:
        items = [s for s in settings.SETTINGS if show_all or s.group == settings.BASIC]
        io.say("\nเลือกค่าที่จะแก้")
        options = []
        for s in items:
            options.append((s.key, f"{s.label}: {commands.display_value(ctx, s)}"))
        options.append(("_more", "แสดงค่าขั้นสูงทั้งหมด" if not show_all else "ซ่อนค่าขั้นสูง"))
        options.append(("_back", "กลับเมนูหลัก"))
        choice = io.choose("เลือกข้อ", options, default="_back")
        if choice == "_back":
            return 0
        if choice == "_more":
            show_all = not show_all
            continue
        s = settings.BY_KEY[choice]
        if s.note:
            io.say(f"  {s.note}")
        if s.kind == "choice":
            value = io.choose(f"ค่าใหม่ของ {s.key}", [(c, c) for c in s.choices],
                              default=commands.env_value(ctx, s.key) or s.default)
            commands.config_set(ctx, s.key, value)
        elif s.key == "OLLAMA_MODEL":
            models = ctx.models_fn(commands.env_value(ctx, "OLLAMA_URL", engine.DEFAULT_OLLAMA_URL))
            if models:
                current = commands.env_value(ctx, s.key) or s.default
                value = io.choose("เลือกโมเดลใน Ollama", [(m, m) for m in models],
                                  default=current if engine.model_present(models, current) else models[0])
                commands.config_set(ctx, s.key, value)
            else:
                io.say("ติดต่อ Ollama ไม่ได้ พิมพ์ชื่อโมเดลเอง หรือเปิด Ollama แล้วลองใหม่")
                commands.config_set(ctx, s.key)
        else:
            commands.config_set(ctx, s.key)


def new_tool_menu(ctx: Context) -> int:
    io = ctx.io
    io.say(f"tool ที่มีอยู่: {', '.join(scaffold.existing_tools(ctx.root / 'agent-kit' / 'tools')) or 'ยังไม่มี'}")
    name = io.ask("ตั้งชื่อ tool ใหม่ (ตัวพิมพ์เล็ก a-z ตัวเลข _ เช่น check_stock)")
    return commands.new_tool(ctx, name) if name else 2


def run_menu(ctx: Context) -> int:
    io = ctx.io
    actions = {
        K["setup"]: lambda: commands.setup(ctx),
        K["demo"]: lambda: commands.demo(ctx),
        K["docs"]: lambda: docs_menu(ctx),
        K["ask"]: lambda: commands.ask(ctx),
        K["agent"]: lambda: commands.agent(ctx),
        K["settings"]: lambda: settings_menu(ctx),
        K["status"]: lambda: commands.status(ctx),
        K["tool"]: lambda: new_tool_menu(ctx),
    }
    while True:
        suggested, hint = commands.next_step(ctx)
        io.say(f"\n{'=' * 60}\n{TITLE}\n{'=' * 60}")
        io.say(f"ขั้นต่อไปที่แนะนำ: {hint}\n")
        try:
            choice = io.pick("พิมพ์เลขข้อแล้วกด Enter", MENU, default=suggested)
        except Cancelled:
            io.say("\nออกจากโปรแกรม")
            return 0
        if choice == "0":
            io.say("ออกจากโปรแกรม")
            return 0
        try:
            actions[choice]()
            if choice != K["settings"]:
                _pause(ctx)
        except Cancelled:
            io.say("\nยกเลิกรายการนี้ กลับเมนูหลัก")
