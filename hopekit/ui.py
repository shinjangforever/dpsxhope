"""การรับและแสดงข้อความกับผู้ใช้ แยกออกมาเพื่อให้ทดสอบด้วยคำตอบที่เตรียมไว้ได้"""
import getpass
import sys

_YES = {"y", "yes", "ok", "ใช่", "ใช้", "ตกลง"}
_NO = {"n", "no", "ไม่", "ไม่ใช่", "ยกเลิก"}


class Cancelled(Exception):
    """ผู้ใช้กด Ctrl+C หรือปิด input กลางทาง"""


class ConsoleIO:
    def say(self, text: str = "") -> None:
        print(text, flush=True)

    def ask(self, prompt: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        try:
            answer = input(f"{prompt}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise Cancelled() from None
        return answer or default

    def secret(self, prompt: str) -> str:
        """รับค่าลับโดยไม่แสดงตัวอักษรบนหน้าจอ (ถ้า input ไม่ใช่หน้าจอจริงจะอ่านแบบปกติ)"""
        try:
            if sys.stdin.isatty():
                return getpass.getpass(f"{prompt}: ").strip()
            return input(f"{prompt}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise Cancelled() from None

    def confirm(self, prompt: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        for _ in range(3):
            answer = self.ask(f"{prompt} ({hint})").lower()
            if not answer:
                return default
            if answer in _YES:
                return True
            if answer in _NO:
                return False
            self.say("พิมพ์ y (ใช่) หรือ n (ไม่ใช่)")
        return default

    def pick(self, prompt: str, options: list[tuple[str, str]], default: str | None = None) -> str:
        """แสดงรหัสของตัวเลือกตามจริง (ใช้กับเมนูที่มีข้อ 0 สำหรับออก) แล้วคืนรหัสที่พิมพ์"""
        keys = [k for k, _ in options]
        default = default if default in keys else keys[0]
        for key, label in options:
            tag = "  <- กด Enter" if key == default else ""
            self.say(f"  {key}  {label}{tag}")
        for _ in range(3):
            answer = self.ask(prompt, default)
            if answer in keys:
                return answer
            self.say(f"พิมพ์ตัวเลขข้อที่ต้องการ ({', '.join(keys)})")
        return default

    def choose(self, prompt: str, options: list[tuple[str, str]], default: str | None = None) -> str:
        """แสดงตัวเลือกเป็นข้อ ๆ รับเลขข้อหรือรหัสของตัวเลือก คืนรหัสของตัวเลือกที่เลือก"""
        keys = [k for k, _ in options]
        default = default if default in keys else keys[0]
        numbered = [(str(number), label) for number, (_, label) in enumerate(options, 1)]
        picked = self.pick(prompt, numbered, default=str(keys.index(default) + 1))
        return keys[int(picked) - 1]
