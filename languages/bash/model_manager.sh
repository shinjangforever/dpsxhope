#!/usr/bin/env bash
# model_manager.sh — จัดการ local LLM models (Ollama + llama.cpp)
# รัน: bash model_manager.sh [command]

set -euo pipefail

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
mkdir -p "$MODELS_DIR"

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR]${NC}  $*" >&2; }

# ── Commands ─────────────────────────────────────────────────

cmd_list() {
  info "Ollama models:"
  if command -v ollama &>/dev/null; then
    ollama list 2>/dev/null || warn "ollama not running (ollama serve)"
  else
    warn "ollama not installed"
  fi

  echo ""
  info "GGUF models in $MODELS_DIR:"
  find "$MODELS_DIR" -name "*.gguf" -printf "  %f (%s bytes)\n" 2>/dev/null || \
    echo "  (none found)"
}

cmd_pull() {
  local model="${1:-llama3.2}"
  info "pulling $model via ollama..."
  ollama pull "$model"
  ok "$model ready"
}

cmd_bench() {
  local model="${1:-llama3.2}"
  local prompt="Explain embeddings in one sentence."
  info "benchmarking $model..."

  local start end elapsed
  start=$(date +%s%N)
  reply=$(ollama run "$model" "$prompt" 2>/dev/null)
  end=$(date +%s%N)
  elapsed=$(( (end - start) / 1000000 ))

  echo "  reply:   $reply"
  echo "  latency: ${elapsed}ms"
}

cmd_health() {
  info "checking services..."

  # Ollama
  if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    ok "Ollama     → http://localhost:11434 (running)"
  else
    warn "Ollama     → not running (start: ollama serve)"
  fi

  # llama.cpp server
  if curl -sf http://localhost:8080/health &>/dev/null; then
    ok "llama.cpp  → http://localhost:8080 (running)"
  else
    warn "llama.cpp  → not running (start: bash llamacpp/server.sh model.gguf)"
  fi

  # LM Studio
  if curl -sf http://localhost:1234/v1/models &>/dev/null; then
    ok "LM Studio  → http://localhost:1234 (running)"
  else
    warn "LM Studio  → not running"
  fi
}

cmd_quick_test() {
  local endpoint="${1:-http://localhost:11434}"
  local prompt="Reply with exactly: OK"

  info "quick test: $endpoint"
  if [[ "$endpoint" == *"11434"* ]]; then
    result=$(curl -sf "$endpoint/api/generate" \
      -d "{\"model\":\"llama3.2\",\"prompt\":\"$prompt\",\"stream\":false}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['response'])" 2>/dev/null)
  else
    result=$(curl -sf "$endpoint/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"model\":\"local\",\"messages\":[{\"role\":\"user\",\"content\":\"$prompt\"}]}" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null)
  fi

  if [[ "$result" == *"OK"* ]]; then
    ok "response: $result"
  else
    err "unexpected response: $result"
  fi
}

# ── Entrypoint ────────────────────────────────────────────────

usage() {
  echo "Usage: $0 <command> [args]"
  echo ""
  echo "Commands:"
  echo "  list              — แสดง models ที่มี"
  echo "  pull <model>      — ดาวน์โหลด model ผ่าน Ollama"
  echo "  bench <model>     — benchmark latency"
  echo "  health            — ตรวจสอบ services ที่รันอยู่"
  echo "  test [url]        — quick API test"
  echo ""
  echo "Examples:"
  echo "  $0 pull llama3.2"
  echo "  $0 bench qwen2.5:7b"
  echo "  $0 test http://localhost:8080"
}

case "${1:-help}" in
  list)   cmd_list ;;
  pull)   cmd_pull "${2:-llama3.2}" ;;
  bench)  cmd_bench "${2:-llama3.2}" ;;
  health) cmd_health ;;
  test)   cmd_quick_test "${2:-http://localhost:11434}" ;;
  *)      usage ;;
esac
