"""
workflow_runner.py — รัน agent workflow แบบ multi-step
workflow = ลำดับ steps ที่แต่ละ step ใช้ LLM + tools + เงื่อนไขแตกต่างกัน

รัน: python workflow_runner.py templates/research_workflow.json "What is RAG?"
"""
from __future__ import annotations
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_ROOT))
load_dotenv()

import tools as registry

# ── Data types ────────────────────────────────────────────────

@dataclass
class WorkflowStep:
    name: str
    system: str
    prompt_template: str       # ใช้ {input}, {prev_output}, {context}
    model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-haiku-5-5"))
    max_tokens: int = 1024
    tools: list[str] = field(default_factory=list)
    condition: Optional[str] = None   # "always" | "if_prev_success"


@dataclass
class StepResult:
    step_name: str
    output: str
    success: bool
    latency_ms: int
    tokens_used: int
    error: Optional[str] = None


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

def run_step(
    step: WorkflowStep,
    user_input: str,
    prev_output: str = "",
    context: dict[str, Any] | None = None,
) -> StepResult:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ตั้ง ANTHROPIC_API_KEY ในไฟล์ .env ที่ root ของ repo ก่อน")
    client = anthropic.Anthropic()
    ctx = context or {}

    prompt = step.prompt_template.format(
        input=user_input,
        prev_output=prev_output,
        **ctx,
    )

    start = time.perf_counter()
    try:
        if step.tools:
            # agentic loop
            tools = registry.select(step.tools)
            tool_schemas = [tool.schema for tool in tools.values()]
            text = ""
            messages = [{"role": "user", "content": prompt}]
            total_tokens = 0

            for _ in range(6):
                resp = client.messages.create(
                    model=step.model,
                    max_tokens=step.max_tokens,
                    system=step.system,
                    tools=tool_schemas,
                    messages=messages,
                )
                total_tokens += resp.usage.input_tokens + resp.usage.output_tokens

                if resp.stop_reason != "tool_use":
                    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
                    break
                messages.append({"role": "assistant", "content": resp.content})
                results = []
                for block in resp.content:
                    if block.type != "tool_use":
                        continue
                    result = registry.run(tools, block.name, block.input)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                        "is_error": "error" in result,
                    })
                messages.append({"role": "user", "content": results})
        else:
            resp = client.messages.create(
                model=step.model,
                max_tokens=step.max_tokens,
                system=step.system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            total_tokens = resp.usage.input_tokens + resp.usage.output_tokens

        return StepResult(
            step_name=step.name,
            output=text,
            success=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            tokens_used=total_tokens,
        )

    except Exception as exc:
        return StepResult(
            step_name=step.name, output="", success=False,
            latency_ms=int((time.perf_counter() - start) * 1000),
            tokens_used=0, error=str(exc),
        )


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
                print(f"   ✗ error: {result.error}")

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
    print(f"✅ Done | {result.total_ms}ms | {result.total_tokens} tokens")
    print(f"\nFinal output:\n{result.final_output}")
