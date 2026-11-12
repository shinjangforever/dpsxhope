"""
workflow_runner.py — รัน agent workflow แบบ multi-step ทีละขั้นตามลำดับ
workflow = ลำดับ steps ที่แต่ละ step ใช้ LLM + tools + เงื่อนไขแตกต่างกัน

รัน: python workflow_runner.py templates/research_workflow.json "What is RAG?"
ใช้ได้ทั้ง Claude และ Ollama (ตั้ง LLM_PROVIDER) ดู ../llm.py
"""
from __future__ import annotations
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

AGENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_ROOT))

import llm  # noqa: E402
import tools as registry  # noqa: E402

llm.load_env()

# ── Data types ────────────────────────────────────────────────

@dataclass
class WorkflowStep:
    name: str
    system: str
    prompt_template: str       # ใช้ {input}, {prev_output}, {context}
    model: Optional[str] = None       # ไม่ระบุ = โมเดลตามค่าตั้ง (CLAUDE_MODEL หรือ OLLAMA_MODEL)
    max_tokens: int = 1024
    tools: list[str] = field(default_factory=list)
    condition: Optional[str] = None   # "always" | "if_prev_success"
    retries: int = 0                  # ลองซ้ำกี่ครั้งเมื่อขั้นนี้ล้ม (รอ 1, 2, 4 ... วินาที)


@dataclass
class StepResult:
    step_name: str
    output: str
    success: bool
    latency_ms: int
    tokens_used: int
    error: Optional[str] = None
    attempts: int = 1


@dataclass
class WorkflowResult:
    workflow_name: str
    steps: list[StepResult]
    final_output: str
    total_ms: int
    total_tokens: int

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)


# ── Step executor ─────────────────────────────────────────────

def _attempt(step: WorkflowStep, prompt: str) -> tuple[str, int]:
    if step.tools:
        tools = registry.select(step.tools)
        result = llm.tool_loop(prompt, tools, registry.run, system=step.system, max_turns=6,
                               max_tokens=step.max_tokens, model=step.model)
        if not result.finished:
            raise RuntimeError("ครบ 6 รอบแล้วโมเดลยังขอเรียก tool อยู่")
        return result.text, result.tokens
    reply = llm.chat([{"role": "user", "content": prompt}], system=step.system,
                     max_tokens=step.max_tokens, model=step.model)
    return reply.text, reply.tokens


def run_step(
    step: WorkflowStep,
    user_input: str,
    prev_output: str = "",
    context: dict[str, Any] | None = None,
    sleep=time.sleep,
) -> StepResult:
    issue = llm.problem()
    if issue:
        raise SystemExit(issue)
    prompt = step.prompt_template.format(input=user_input, prev_output=prev_output, **(context or {}))

    start = time.perf_counter()
    error = ""
    for attempt in range(1, step.retries + 2):
        try:
            text, tokens = _attempt(step, prompt)
            return StepResult(step.name, text, True, int((time.perf_counter() - start) * 1000), tokens,
                              attempts=attempt)
        except Exception as exc:
            error = str(exc)
            if attempt <= step.retries:
                sleep(2 ** (attempt - 1))
    return StepResult(step.name, "", False, int((time.perf_counter() - start) * 1000), 0,
                      error=error, attempts=step.retries + 1)


# ── Workflow runner ───────────────────────────────────────────

def run_workflow(
    steps: list[WorkflowStep],
    user_input: str,
    workflow_name: str = "workflow",
    context: dict[str, Any] | None = None,
    verbose: bool = True,
) -> WorkflowResult:
    results: list[StepResult] = []
    prev_output = ""
    start = time.perf_counter()

    for step in steps:
        # ตรวจ condition
        if step.condition == "if_prev_success" and results and not results[-1].success:
            if verbose:
                print(f"  ⏭  [{step.name}] skipped (prev step failed)")
            continue

        if verbose:
            print(f"\n▶  [{step.name}]")

        result = run_step(step, user_input, prev_output, context)
        results.append(result)
        prev_output = result.output

        if verbose:
            if result.success:
                preview = result.output[:120].replace("\n", " ")
                print(f"   ✓ {result.latency_ms}ms | {result.tokens_used} tokens")
                print(f"   → {preview}{'...' if len(result.output) > 120 else ''}")
            else:
                print(f"   ✗ error (ลอง {result.attempts} ครั้ง): {result.error}")

    return WorkflowResult(
        workflow_name=workflow_name,
        steps=results,
        final_output=prev_output,
        total_ms=int((time.perf_counter() - start) * 1000),
        total_tokens=sum(r.tokens_used for r in results),
    )


# ── Load workflow from JSON ───────────────────────────────────

def load_workflow(path: str) -> tuple[str, list[WorkflowStep]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    steps = [WorkflowStep(**s) for s in data["steps"]]
    return data.get("name", path), steps


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python workflow_runner.py <workflow.json> <input>")
        print("Example: python workflow_runner.py templates/research_workflow.json 'What is RAG?'")
        sys.exit(1)

    wf_path = sys.argv[1]
    user_input = " ".join(sys.argv[2:])

    name, steps = load_workflow(wf_path)
    print(f"\n=== {name} ===")
    print(f"input: {user_input}\n")

    result = run_workflow(steps, user_input, name)

    print(f"\n{'='*50}")
    print(f"{'✅ Done' if result.success else '❌ Failed'} | {result.total_ms}ms | {result.total_tokens} tokens")
    print(f"\nFinal output:\n{result.final_output}")
    sys.exit(0 if result.success else 1)
