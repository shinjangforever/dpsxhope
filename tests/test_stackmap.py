"""ทดสอบแผนที่ stack (hopekit/stackmap.py และ stack/stack.json)

ตรวจว่า: คลังข้อมูลถูกต้องและชี้ไปยังไฟล์ที่มีจริง, ทุกสายมีครบทุกระดับ, เอกสารที่สร้างตรงกับคลังข้อมูล,
มุมมองใน terminal กรองตามกลุ่ม สาย ระดับได้ถูก และคลังที่ผิดถูกจับได้
ไม่ตรวจ: ความถูกต้องของคำอธิบายเครื่องมือแต่ละชิ้น (ต้องให้คนอ่านตรวจ)
"""
import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hopekit import stackmap  # noqa: E402

S = stackmap.load(ROOT)


def capture(fn, *args, **kwargs):
    lines = []
    code = fn(S, lines.append, *args, **kwargs)
    return code, "\n".join(lines)


class DataTest(unittest.TestCase):
    def test_data_is_valid(self):
        self.assertEqual(stackmap.problems(S.data, ROOT), [])

    def test_shape_matches_what_the_docs_promise(self):
        self.assertEqual(sorted(S.levels), [1, 2, 3, 4])
        self.assertEqual(len(S.knowledge), len(S.tracks) * len(S.levels))
        for wanted in ("agent", "automation", "fullstack", "security", "math", "philosophy"):
            self.assertIn(wanted, S.tracks)
        for group in S.groups:
            self.assertTrue(S.select(group=group), group)
        self.assertEqual(len({t["id"] for t in S.tools}), len(S.tools))

    def test_every_tool_is_explained(self):
        for tool in S.tools:
            with self.subTest(tool=tool["id"]):
                self.assertGreater(len(tool["what"]), 15)
                self.assertGreater(len(tool["when"]), 15)
                self.assertNotEqual(tool["what"], tool["when"])

    def test_every_track_starts_with_something_usable(self):
        # ระดับ 1 ของทุกสายต้องมีเนื้อหาในคู่มือให้เริ่มได้ทันที
        for track in S.tracks:
            self.assertTrue(S.cell(track, 1)["where"], track)

    def test_problems_are_caught(self):
        bad = copy.deepcopy(S.data)
        bad["tools"][0].update(group="nope", level=9, tracks=["ghost"], in_repo="no/such/file.py", what=" ")
        bad["tools"].append(dict(bad["tools"][1]))
        bad["knowledge"] = [k for k in bad["knowledge"] if not (k["track"] == "agent" and k["level"] == 4)]
        bad["knowledge"][0]["where"] = ["missing.md"]
        bad["groups"].append({"id": "empty", "name": "ว่าง", "about": "-"})
        text = "\n".join(stackmap.problems(bad, ROOT))
        for expected in ("ไม่มีกลุ่ม nope", "ไม่มีระดับ 9", "ไม่มีสาย ghost", "ไม่พบ no/such/file.py", "what ว่าง",
                         "id ซ้ำ", "สาย agent ยังไม่มีความรู้ระดับ 4", "ไม่พบ missing.md", "กลุ่ม empty ไม่มีเครื่องมือ"):
            self.assertIn(expected, text)


class DocsTest(unittest.TestCase):
    def test_generated_docs_are_up_to_date(self):
        for name, render in stackmap.DOCS.items():
            with self.subTest(doc=name):
                on_disk = (ROOT / name).read_text(encoding="utf-8")
                self.assertEqual(on_disk, render(S), f"{name} ไม่ตรงกับ stack.json รัน: python hope.py stack docs")

    def test_docs_cover_everything(self):
        tools_md = stackmap.render_tools_md(S)
        paths_md = stackmap.render_paths_md(S)
        for tool in S.tools:
            self.assertIn(f"**{tool['name']}**", tools_md)
        for group in S.groups.values():
            self.assertIn(f"## {group['name']}", tools_md)
        for track in S.tracks.values():
            self.assertIn(f"## {track['name']}", paths_md)
        self.assertEqual(paths_md.count("ยังไม่มีเนื้อหา |"), sum(not k["where"] for k in S.knowledge))

    def test_readme_names_every_group_track_and_level(self):
        readme = (ROOT / "stack" / "README.md").read_text(encoding="utf-8")
        for item in list(S.groups.values()) + list(S.tracks.values()) + list(S.levels.values()):
            self.assertIn(item["name"], readme)
        self.assertIn(f"{len(S.tools)} ชิ้น", readme)
        # ตารางกลุ่มใน README ต้องเอ่ยชื่อเครื่องมือครบทุกชิ้น
        missing = [t["name"] for t in S.tools if t["name"].split(" (")[0] not in readme]
        self.assertEqual(missing, [])


class ViewsTest(unittest.TestCase):
    def test_tools_filters(self):
        code, text = capture(stackmap.show_tools, group="language")
        self.assertEqual(code, 0)
        self.assertIn("Python", text)
        self.assertNotIn("Ollama", text)
        code, text = capture(stackmap.show_tools, track="security", level=3)
        names = {t["name"] for t in S.select(track="security", level=3)}
        self.assertTrue(names)
        for name in names:
            self.assertIn(name, text)
        self.assertNotIn("robokit", text)
        self.assertEqual(capture(stackmap.show_tools, group="science", level=1)[0], 1)

    def test_tools_marks_what_this_machine_has(self):
        _code, text = capture(stackmap.show_tools, group="language", have={"python": "3.13", "go": None})
        lines = {line.split("]")[1].split()[0]: line for line in text.splitlines() if "] " in line and line.startswith("  ")}
        self.assertTrue(lines["Python"].lstrip().startswith("+"))
        self.assertTrue(lines["Go"].lstrip().startswith("-"))
        self.assertTrue(lines["SQL"].lstrip().startswith("["))          # ตรวจไม่ได้ จึงไม่ใส่เครื่องหมาย

    def test_show_one_tool_and_suggest_close_names(self):
        code, text = capture(stackmap.show_tool, "OLLAMA", have={"ollama": None})
        self.assertEqual(code, 0)
        for expected in ("กลุ่ม", "ระดับ", "สาย", "คืออะไร", "ใช้เมื่อ", "ยังไม่มี"):
            self.assertIn(expected, text)
        code, text = capture(stackmap.show_tool, "docker")
        self.assertEqual(code, 0)
        code, text = capture(stackmap.show_tool, "audit")
        self.assertEqual(code, 1)
        self.assertIn("audit-log", text)
        self.assertEqual(capture(stackmap.show_tool, "zzz")[0], 1)

    def test_path_walks_every_level(self):
        code, text = capture(stackmap.show_path, "automation")
        self.assertEqual(code, 0)
        for level in S.levels.values():
            self.assertIn(f"ระดับ {level['id']} {level['name']}", text)
        self.assertIn("ยังไม่มีเนื้อหาในคู่มือนี้", text)                 # ระดับ 4 ของสายนี้ยังว่าง และบอกตรงๆ
        _code, only = capture(stackmap.show_path, "automation", 2)
        self.assertIn("ระดับ 2", only)
        self.assertNotIn("ระดับ 3", only)

    def test_map_lists_all_axes(self):
        _code, text = capture(stackmap.show_map)
        for item in list(S.tracks.values()) + list(S.levels.values()) + list(S.groups.values()):
            self.assertIn(item["name"], text)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "hope.py"), "stack", *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=120, env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def test_command_line(self):
        self.assertIn("Cybersecurity", self.run_cli("map").stdout)
        self.assertIn("PID", self.run_cli("path", "robotics", "--level", "2").stdout)
        self.assertIn("FAISS", self.run_cli("tools", "--track", "data").stdout)
        self.assertEqual(self.run_cli("show", "python").returncode, 0)
        for bad in (("path", "nope"), ("tools", "--group", "nope"), ("tools", "--track", "nope"), ("path",), ("show",)):
            self.assertEqual(self.run_cli(*bad).returncode, 2, bad)


if __name__ == "__main__":
    unittest.main()
