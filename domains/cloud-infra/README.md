# Cloud & Infrastructure for AI Systems

> สถาปัตยกรรม cloud สำหรับ deploy AI workloads — ตั้งแต่ dev laptop ถึง production cluster

---

## Stack ที่ใช้ในโปรเจกต์นี้

| Layer | Tool | ทำอะไร |
|-------|------|---------|
| Container | Docker + Compose | package + รัน services |
| Orchestration | Kubernetes (K8s) | scale + manage containers |
| IaC | Terraform | provision cloud resources |
| CI/CD | GitHub Actions | test + deploy อัตโนมัติ |
| Monitoring | Prometheus + Grafana | metrics + dashboard |
| Secrets | HashiCorp Vault / env | จัดการ API keys |

---

## Local Dev Stack

```bash
# รัน AI stack ทั้งหมดด้วยคำสั่งเดียว
docker compose -f languages/yaml/ai_stack.docker-compose.yml up -d

# ตรวจสอบ
docker ps
curl http://localhost:3000/health   # ai-api
curl http://localhost:11434/api/tags # ollama
```

---

## Kubernetes Deployment (Production)

```yaml
# k8s/ai-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-api
  template:
    spec:
      containers:
        - name: ai-api
          image: ghcr.io/shinjangforever/dpsxhope-ai-api:latest
          ports:
            - containerPort: 3000
          env:
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ai-secrets
                  key: anthropic-api-key
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: ai-api-service
spec:
  selector:
    app: ai-api
  ports:
    - port: 80
      targetPort: 3000
  type: LoadBalancer
```

---

## Terraform — Cloud LLM Instance (AWS)

```hcl
# main.tf — GPU instance สำหรับรัน local model บน cloud

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

resource "aws_instance" "llm_server" {
  ami           = "ami-0c55b159cbfafe1f0"   # Ubuntu 22.04
  instance_type = "g4dn.xlarge"             # 16 GB RAM, T4 GPU (~$0.52/hr)

  user_data = <<-EOF
    #!/bin/bash
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull llama3.1:8b
    systemctl enable ollama
  EOF

  tags = { Name = "dpsxhope-llm" }
}

output "llm_url" {
  value = "http://${aws_instance.llm_server.public_ip}:11434"
}
```

---

## GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy AI API

on:
  push:
    branches: [main]
    paths: ["ai-api/**"]

jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Test API
        run: |
          cd ai-api
          npm ci
          npm test

      - name: Build & push Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./ai-api
          push: true
          tags: ghcr.io/${{ github.repository }}/ai-api:latest

      - name: Deploy to K8s
        run: kubectl apply -f k8s/ai-api-deployment.yaml
```

---

## Monitoring — Prometheus metrics ที่ควร track

```python
# ตัวอย่าง metrics สำหรับ AI API (Python Prometheus client)
from prometheus_client import Counter, Histogram, Gauge

llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status']
)

llm_latency_seconds = Histogram(
    'llm_latency_seconds',
    'LLM response latency',
    ['provider', 'model'],
    buckets=[0.5, 1, 2, 5, 10, 30]
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total tokens used',
    ['provider', 'model', 'direction']   # direction: input | output
)

active_sessions = Gauge('active_sessions', 'Active user sessions')
```

---

## Cost Optimization

| กลยุทธ์ | ประหยัดได้ | วิธี |
|---------|-----------|------|
| Model tiering | 60-80% | ใช้ Haiku/Flash สำหรับงานง่าย, Opus สำหรับงานซับซ้อน |
| Prompt caching | 50-90% | Anthropic prompt cache สำหรับ system prompt ยาวๆ |
| Local models | 100% | Ollama/llama.cpp สำหรับ dev + low-sensitivity tasks |
| Response caching | varies | Redis cache สำหรับ query ซ้ำๆ |
| Batch processing | 50% | Anthropic Batch API สำหรับงาน async |
