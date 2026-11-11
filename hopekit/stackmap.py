"""แผนที่ stack จาก stack/stack.json: เครื่องมือและภาษาจัดเป็นกลุ่ม แยกตามสายและระดับ พร้อมกลุ่มความรู้ของแต่ละช่อง

กลุ่ม  = เครื่องมือชนิดเดียวกัน (ภาษา โมเดล ข้อมูล ...)
สาย   = เป้าหมายของงาน (AI agent, งานอัตโนมัติ, Full stack ...)
ระดับ = ความลึก 1-4 ที่เริ่มต้องใช้เครื่องมือหรือความรู้นั้น
ไฟล์ stack/TOOLS.md และ stack/PATHS.md สร้างจากข้อมูลชุดเดียวกันด้วย python hope.py stack docs
"""
import json
from pathlib import Path
from typing import Callable

DATA = "stack/stack.json"
GENERATED = "<!-- ไฟล์นี้สร้างจาก stack/stack.json ด้วย python hope.py stack docs อย่าแก้ตรงนี้ -->"


class StackData:
    def __init__(self, data: dict):
        self.data = data
        self.levels = {lv["id"]: lv for lv in data["levels"]}
        self.tracks = {t["id"]: t for t in data["tracks"]}
        self.groups = {g["id"]: g for g in data["groups"]}
        self.tools = data["tools"]
        self.knowledge = data["knowledge"]

    def find(self, word: str) -> dict | None:
        """หาเครื่องมือจาก id หรือชื่อ (ไม่สนตัวพิมพ์)"""
        word = word.strip().lower()
        for tool in self.tools:
            if word in (tool["id"].lower(), tool["name"].lower()):
                return tool
        return None

    def select(self, group: str | None = None, track: str | None = None, level: int | None = None) -> list[dict]:
        return [t for t in self.tools
                if (group is None or t["group"] == group)
                and (track is None or track in t["tracks"])
                and (level is None or t["level"] == level)]

    def cell(self, track: str, level: int) -> dict | None:
        return next((k for k in self.knowledge if k["track"] == track and k["level"] == level), None)


def load(root: Path) -> StackData:
    return StackData(json.loads((root / DATA).read_text(encoding="utf-8")))


def problems(data: dict, root: Path) -> list[str]:
    """ตรวจคลังข้อมูล: อ้างกลุ่ม สาย ระดับที่มีจริง, ที่อยู่ไฟล์มีจริง, ทุกสายมีครบทุกระดับ"""
    out: list[str] = []
    levels = {lv["id"] for lv in data.get("levels", [])}
    tracks = {t["id"] for t in data.get("tracks", [])}
    groups = {g["id"] for g in data.get("groups", [])}
    seen: set[str] = set()
    for tool in data.get("tools", []):
        name = tool.get("id", "?")
        for key in ("id", "name", "group", "level", "tracks", "what", "when", "in_repo"):
            if key not in tool:
                out.append(f"{name}: ขาดฟิลด์ {key}")
        if name in seen:
            out.append(f"id ซ้ำ: {name}")
        seen.add(name)
        if tool.get("group") not in groups:
            out.append(f"{name}: ไม่มีกลุ่ม {tool.get('group')}")
        if tool.get("level") not in levels:
            out.append(f"{name}: ไม่มีระดับ {tool.get('level')}")
        if not tool.get("tracks"):
            out.append(f"{name}: ต้องอยู่อย่างน้อยหนึ่งสาย")
        for track in tool.get("tracks", []):
            if track not in tracks:
                out.append(f"{name}: ไม่มีสาย {track}")
        if tool.get("in_repo") and not (root / tool["in_repo"]).exists():
            out.append(f"{name}: ไม่พบ {tool['in_repo']}")
        for key in ("what", "when"):
            if not str(tool.get(key, "")).strip():
                out.append(f"{name}: {key} ว่าง")
    cells = set()
    for item in data.get("knowledge", []):
        where = f"{item.get('track')}/{item.get('level')}"
        if item.get("track") not in tracks or item.get("level") not in levels:
            out.append(f"ความรู้ {where}: สายหรือระดับไม่มีจริง")
        if (item.get("track"), item.get("level")) in cells:
            out.append(f"ความรู้ {where}: ซ้ำ")
        cells.add((item.get("track"), item.get("level")))
        if not item.get("topics") or not str(item.get("can", "")).strip():
            out.append(f"ความรู้ {where}: ต้องมี topics และ can")
        for path in item.get("where", []):
            if not (root / path).exists():
                out.append(f"ความรู้ {where}: ไม่พบ {path}")
    for track in sorted(tracks):
        for level in sorted(levels):
            if (track, level) not in cells:
                out.append(f"สาย {track} ยังไม่มีความรู้ระดับ {level}")
    for group in sorted(groups):
        if not any(t.get("group") == group for t in data.get("tools", [])):
            out.append(f"กลุ่ม {group} ไม่มีเครื่องมือ")
    return out


# ---------- มุมมองใน terminal ----------

def _mark(tool: dict, have: dict | None) -> str:
    """เครื่องหมายว่าเครื่องนี้มีเครื่องมือไหม (เฉพาะตัวที่ตรวจได้)"""
    if have is None or "check" not in tool:
        return " "
    return "+" if have.get(tool["check"]) else "-"


def _tool_line(s: StackData, tool: dict, have: dict | None) -> str:
    return f"  {_mark(tool, have)} [{tool['level']}] {tool['name']:<30} {tool['what']}"


def show_tools(s: StackData, say: Callable, group=None, track=None, level=None, have: dict | None = None) -> int:
    chosen = s.select(group, track, level)
    if not chosen:
        say("ไม่มีเครื่องมือที่ตรงเงื่อนไข")
        return 1
    filters = [s.groups[group]["name"] if group else "", s.tracks[track]["name"] if track else "",
               f"ระดับ {level} {s.levels[level]['name']}" if level else ""]
    say("เครื่องมือและภาษา" + (": " + " · ".join(f for f in filters if f) if any(filters) else " ทั้งหมด")
        + f" ({len(chosen)} ชิ้น)")
    for g in s.groups.values():
        items = sorted((t for t in chosen if t["group"] == g["id"]), key=lambda t: (t["level"], t["name"].lower()))
        if not items:
            continue
        say(f"\n== {g['name']} — {g['about']} ==")
        for tool in items:
            say(_tool_line(s, tool, have))
    say("\n[เลข] = ระดับที่เริ่มต้องใช้" + ("   + มีในเครื่องนี้   - ยังไม่มี" if have is not None else ""))
    say("ดูรายละเอียดทีละชิ้น: python hope.py stack show ชื่อ")
    return 0


def show_tool(s: StackData, say: Callable, word: str, have: dict | None = None) -> int:
    tool = s.find(word)
    if not tool:
        close = [t["id"] for t in s.tools if word.lower() in t["id"].lower() or word.lower() in t["name"].lower()]
        say(f"ไม่พบ {word}" + (f" ใกล้เคียง: {', '.join(close)}" if close else " ดูรายการด้วย: python hope.py stack tools"))
        return 1
    level = s.levels[tool["level"]]
    say(f"{tool['name']}  ({tool['id']})")
    say(f"  กลุ่ม      {s.groups[tool['group']]['name']}")
    say(f"  ระดับ      {level['id']} {level['name']} — {level['means']}")
    say(f"  สาย        {', '.join(s.tracks[t]['name'] for t in tool['tracks'])}")
    say(f"  คืออะไร    {tool['what']}")
    say(f"  ใช้เมื่อ    {tool['when']}")
    say(f"  ในคู่มือ   {tool['in_repo'] or 'ยังไม่มีตัวอย่างในคู่มือนี้'}")
    if have is not None and "check" in tool:
        say(f"  เครื่องนี้  {have.get(tool['check']) or 'ยังไม่มี'}")
    return 0


def show_path(s: StackData, say: Callable, track: str, level: int | None = None, have: dict | None = None) -> int:
    info = s.tracks[track]
    say(f"สาย {info['name']} — {info['question']}")
    for lv in s.levels.values():
        if level is not None and lv["id"] != level:
            continue
        cell = s.cell(track, lv["id"])
        say(f"\n== ระดับ {lv['id']} {lv['name']}: {lv['means']} ==")
        say(f"  ทำได้เมื่อจบ  {cell['can']}")
        say("  ความรู้")
        for topic in cell["topics"]:
            say(f"    - {topic}")
        tools = sorted(s.select(track=track, level=lv["id"]), key=lambda t: t["name"].lower())
        if tools:
            say("  เครื่องมือที่เริ่มใช้ในระดับนี้")
            for tool in tools:
                say(f"   {_mark(tool, have)} {tool['name']}: {tool['what']}")
        say(f"  ในคู่มือ      {', '.join(cell['where']) if cell['where'] else 'ยังไม่มีเนื้อหาในคู่มือนี้'}")
    return 0


def show_map(s: StackData, say: Callable) -> int:
    say("แผนที่ stack: สาย × ระดับ (ตัวเลข = จำนวนเครื่องมือที่เริ่มใช้ในระดับนั้น, * = มีเนื้อหาในคู่มือแล้ว)\n")
    say(f"  {'สาย':<22}" + "".join(f"{lv['id']} {lv['name']:<12}" for lv in s.levels.values()))
    for track in s.tracks.values():
        row = f"  {track['name']:<22}"
        for lv in s.levels.values():
            cell = s.cell(track["id"], lv["id"])
            count = len(s.select(track=track["id"], level=lv["id"]))
            row += f"{count:>2}{'*' if cell['where'] else ' '}{'':<11}"
        say(row)
    say("\nระดับ")
    for lv in s.levels.values():
        say(f"  {lv['id']} {lv['name']:<10} {lv['means']}")
    say("\nกลุ่มเครื่องมือ")
    for g in s.groups.values():
        say(f"  {g['id']:<10} {g['name']} ({len(s.select(group=g['id']))} ชิ้น)")
    say("\nดูทีละสาย: python hope.py stack path " + "|".join(s.tracks))
    say("ดูเครื่องมือ: python hope.py stack tools [--group กลุ่ม] [--track สาย] [--level 1-4]")
    return 0


# ---------- เอกสารที่สร้างจากข้อมูล ----------

def render_tools_md(s: StackData) -> str:
    lines = [GENERATED, "", "# เครื่องมือและภาษา", "",
             f"รายการที่คัดไว้ {len(s.tools)} ชิ้น จัดเป็น {len(s.groups)} กลุ่ม แต่ละชิ้นบอกว่าคืออะไร ใช้เมื่อไร "
             "เริ่มต้องใช้ที่ระดับไหน อยู่ในสายไหน และมีตัวอย่างในคู่มือนี้ที่ใด "
             "ดูสายและระดับที่ [PATHS.md](PATHS.md) และภาพรวมที่ [README.md](README.md)", "",
             "ดูใน terminal ได้ด้วย `python hope.py stack tools` ซึ่งบอกด้วยว่าเครื่องของคุณมีชิ้นไหนแล้ว", ""]
    for g in s.groups.values():
        lines += [f"## {g['name']}", "", g["about"], "", "| ชื่อ | ระดับ | คืออะไร | ใช้เมื่อ | สาย | ในคู่มือ |", "|---|---|---|---|---|---|"]
        for tool in sorted(s.select(group=g["id"]), key=lambda t: (t["level"], t["name"].lower())):
            where = f"[`{tool['in_repo']}`](../{tool['in_repo']})" if tool["in_repo"] else "ยังไม่มี"
            lines.append(f"| **{tool['name']}** | {tool['level']} {s.levels[tool['level']]['name']} | {tool['what']} | "
                         f"{tool['when']} | {', '.join(s.tracks[t]['name'] for t in tool['tracks'])} | {where} |")
        lines.append("")
    lines += [f"ปรับปรุงข้อมูลล่าสุด {s.data['updated']} คำอธิบายเป็นภาพกว้างสำหรับเลือกเครื่องมือ "
              "รายละเอียดและรุ่นปัจจุบันให้ดูจากเอกสารของเครื่องมือนั้น", ""]
    return "\n".join(lines)


def render_paths_md(s: StackData) -> str:
    lines = [GENERATED, "", "# สายและระดับ", "",
             f"{len(s.tracks)} สาย แต่ละสายมี {len(s.levels)} ระดับ แต่ละช่องบอกความรู้ที่ควรมี สิ่งที่ทำได้เมื่อจบ "
             "เครื่องมือที่เริ่มใช้ และเนื้อหาในคู่มือนี้ คำอธิบายของเครื่องมืออยู่ที่ [TOOLS.md](TOOLS.md)", "",
             "| ระดับ | ชื่อ | ความหมาย |", "|---|---|---|"]
    lines += [f"| {lv['id']} | {lv['name']} | {lv['means']} |" for lv in s.levels.values()]
    lines += ["", "ไม่จำเป็นต้องไปถึงระดับ 4 ทุกสาย เลือกสายตามเป้าหมาย แล้วไปให้ลึกเท่าที่งานต้องการ", ""]
    for track in s.tracks.values():
        lines += [f"## {track['name']}", "", f"คำถามของสายนี้: {track['question']}", "",
                  "| ระดับ | ความรู้ | ทำได้เมื่อจบ | เครื่องมือที่เริ่มใช้ | ในคู่มือ |", "|---|---|---|---|---|"]
        for lv in s.levels.values():
            cell = s.cell(track["id"], lv["id"])
            tools = ", ".join(t["name"] for t in sorted(s.select(track=track["id"], level=lv["id"]),
                                                       key=lambda t: t["name"].lower())) or "-"
            where = ", ".join(f"[`{p}`](../{p})" for p in cell["where"]) or "ยังไม่มีเนื้อหา"
            lines.append(f"| {lv['id']} {lv['name']} | {' · '.join(cell['topics'])} | {cell['can']} | {tools} | {where} |")
        lines.append("")
    lines += ["ช่องที่เขียนว่า \"ยังไม่มีเนื้อหา\" คือความรู้ที่สายนั้นต้องใช้ แต่คู่มือนี้ยังไม่ได้ทำ "
              "ลิงก์ในช่อง \"ในคู่มือ\" ชี้ไปยังต้นแบบหรือเอกสารที่เกี่ยวข้อง ยังไม่ใช่บทเรียนที่เรียงเป็นขั้น", ""]
    return "\n".join(lines)


DOCS = {"stack/TOOLS.md": render_tools_md, "stack/PATHS.md": render_paths_md}


def write_docs(root: Path, say: Callable = print) -> int:
    s = load(root)
    issues = problems(s.data, root)
    if issues:
        for issue in issues:
            say(f"ปัญหา: {issue}")
        return 1
    for name, render in DOCS.items():
        (root / name).write_text(render(s), encoding="utf-8", newline="\n")
        say(f"เขียน {name}")
    return 0
