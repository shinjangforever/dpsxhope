#!/usr/bin/env bash
# server.sh — compile llama.cpp แล้วรัน OpenAI-compatible server
# รัน: bash server.sh /path/to/model.gguf

set -euo pipefail

MODEL="${1:-model.gguf}"
PORT="${2:-8080}"
THREADS="${3:-$(nproc)}"
CTX="${4:-4096}"
REPO_DIR="$HOME/llama.cpp"

# ── Clone / update ────────────────────────────────────
if [[ ! -d "$REPO_DIR" ]]; then
  echo "cloning llama.cpp..."
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$REPO_DIR"
else
  echo "updating llama.cpp..."
  git -C "$REPO_DIR" pull --ff-only
fi

# ── Detect arch + compile flags ───────────────────────
CMAKE_FLAGS=""

if [[ "$(uname -m)" == "x86_64" ]]; then
  # ตรวจ AVX2 support
  if grep -q avx2 /proc/cpuinfo 2>/dev/null; then
    CMAKE_FLAGS="-DGGML_AVX2=ON"
    echo "detected: x86_64 + AVX2"
  else
    echo "detected: x86_64 (no AVX2)"
  fi
elif [[ "$(uname -m)" == "aarch64" ]]; then
  CMAKE_FLAGS="-DGGML_NEON=ON"
  echo "detected: ARM64 / aarch64"
elif [[ "$(uname -m)" == "armv7l" ]]; then
  CMAKE_FLAGS="-DGGML_NEON=ON"
  echo "detected: ARMv7"
fi

# CUDA (ถ้ามี)
if command -v nvcc &>/dev/null; then
  CMAKE_FLAGS="$CMAKE_FLAGS -DGGML_CUDA=ON"
  echo "detected: NVIDIA CUDA"
fi

# ── Build ─────────────────────────────────────────────
echo "building... (threads: $THREADS)"
cmake -B "$REPO_DIR/build" $CMAKE_FLAGS "$REPO_DIR" -DCMAKE_BUILD_TYPE=Release
cmake --build "$REPO_DIR/build" -j"$THREADS" --target llama-server

# ── Run server ────────────────────────────────────────
echo ""
echo "starting llama-server"
echo "  model:   $MODEL"
echo "  port:    $PORT"
echo "  threads: $THREADS"
echo "  context: $CTX tokens"
echo "  url:     http://localhost:$PORT"
echo ""

"$REPO_DIR/build/bin/llama-server" \
  -m "$MODEL" \
  --port "$PORT" \
  -t "$THREADS" \
  --ctx-size "$CTX" \
  --log-disable
