# llama.cpp — Compile Guide (Multi-Architecture)

> เบา · เร็ว · รันบน RAM น้อย · compile บน CPU ใดก็ได้
> ไม่ต้อง GPU, ไม่ต้อง Python, ไม่ต้อง Docker

---

## ทำไมต้อง llama.cpp

| ข้อดี | รายละเอียด |
|-------|-----------|
| RAM น้อย | Q4 quantization — 7B model ใช้แค่ ~4 GB RAM |
| เร็ว | C++ native, SIMD optimized ทุก arch |
| ไม่ต้อง GPU | รัน CPU-only ได้ดีมาก |
| Cross-platform | Linux · macOS · Windows · Android · Raspberry Pi |
| OpenAI-compatible | --server mode expose REST API |

---

## วิธี Compile

### x86_64 (PC / Server ทั่วไป)

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# CPU only (ง่ายสุด)
cmake -B build
cmake --build build -j$(nproc) --config Release

# AVX2 (Intel Haswell+ / AMD Ryzen) — เร็วขึ้น ~30%
cmake -B build -DGGML_AVX2=ON
cmake --build build -j$(nproc)
```

### ARM / Apple Silicon (M1–M4)

```bash
# Metal GPU acceleration (macOS)
cmake -B build -DGGML_METAL=ON
cmake --build build -j$(nproc)

# ARM CPU only (Raspberry Pi, Termux)
cmake -B build -DGGML_NEON=ON
cmake --build build -j4
```

### NVIDIA GPU (CUDA)

```bash
cmake -B build -DGGML_CUDA=ON
cmake --build build -j$(nproc)
```

### AMD GPU (ROCm)

```bash
cmake -B build -DGGML_HIPBLAS=ON -DAMDGPU_TARGETS=gfx1100
cmake --build build -j$(nproc)
```

### Android (Termux)

```bash
pkg install clang cmake git
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && cmake -B build -DGGML_NEON=ON
cmake --build build -j2
```

---

## ดาวน์โหลดโมเดล (.gguf)

```bash
# ตัวอย่าง: Llama 3.2 3B Q4_K_M (~2 GB)
wget https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf

# Qwen 2.5 7B Q4 (~4.5 GB) — ภาษาไทยดี
wget https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf
```

**Quantization เลือกยังไง:**

| Format | Size | Quality | แนะนำ |
|--------|------|---------|--------|
| Q2_K | เล็กสุด | ต่ำสุด | RAM < 4GB |
| Q4_K_M | กลาง | ดี | **แนะนำ** |
| Q5_K_M | ใหญ่กว่า | ดีมาก | RAM > 8GB |
| Q8_0 | ใหญ่ | เกือบเต็ม | RAM > 16GB |

---

## รัน

```bash
# chat โดยตรง
./build/bin/llama-cli -m model.gguf -p "สวัสดี" -n 200

# OpenAI-compatible server (ใช้กับ unified_client.py ได้เลย)
./build/bin/llama-server -m model.gguf --port 8080 --ctx-size 4096

# ปรับ thread ตาม CPU
./build/bin/llama-server -m model.gguf -t 8 --port 8080
```

---

## RAM Reference

| โมเดล | Quant | RAM ที่ต้อง |
|-------|-------|-----------|
| Llama 3.2 3B | Q4_K_M | ~2.5 GB |
| Llama 3.1 8B | Q4_K_M | ~5 GB |
| Mistral 7B | Q4_K_M | ~4.5 GB |
| Qwen2.5 7B | Q4_K_M | ~5 GB |
| Llama 3.1 70B | Q4_K_M | ~42 GB |
