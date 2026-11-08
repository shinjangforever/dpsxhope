<p align="center">
  <img src="assets/banner/banner.png" alt="dpsxhope: an AI knowledge map and real-world blueprints" width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-c9a227" alt="Code license: MIT"></a>
  <a href="LICENSE-CONTENT.md"><img src="https://img.shields.io/badge/content-CC%20BY%204.0-c9a227" alt="Content license: CC BY 4.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-111111" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-20%2B-111111" alt="Node.js 20+">
  <img src="https://img.shields.io/badge/status-building-111111" alt="Status: building">
</p>

<p align="center">
    <a href="#choose-a-blueprint">Choose a blueprint</a> ·
  <a href="#use-your-documents">Use your documents</a> ·
  <a href="ROADMAP.md">Roadmap (Thai)</a> ·
  <a href="README.md">ภาษาไทย</a>
</p>

**dpsxhope** is a Thai-first AI engineering handbook and set of blueprints you can adapt to your own documents, systems, and work.

It starts with RAG, agents, evaluation, and AI APIs. It's growing into a knowledge map that connects AI with robotics, anatomy, biology, quantum computing, business, games, sports, and 3D.

## Choose a blueprint

| Build | Blueprint | Adapt it by | Requires |
|---|---|---|---|
| **Document Q&A** | [`rag-pipeline`](rag-pipeline/) | Adding `.txt`, `.md`, and `.pdf` files plus your test cases | Ollama or an API key |
| **Internal assistant** | [`agent-kit`](agent-kit/) | Adding tool files and a system prompt | API key |
| **AI quality checks** | [`llm-eval`](llm-eval/) | Using your test cases and CI thresholds | Ollama or an API key |
| **AI service** | [`ai-api`](ai-api/) | Setting auth, CORS, prompts, and deployment | Node.js, API key |

Before you open a system to other people, read the [adoption guide](BLUEPRINTS.md). It's currently in Thai.

## Use your documents

You need Git and Python 3.11 or later.

```bash
git clone https://github.com/shinjangforever/dpsxhope.git
cd dpsxhope
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS, Linux, Termux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies and build the index:

```bash
pip install -r rag-pipeline/requirements.txt
cp .env.example .env
cd rag-pipeline
python pipeline.py ingest --docs /path/to/your-docs
```

Choose how to generate answers in `.env`:

| Option | Settings |
|---|---|
| **Local Ollama** | `LLM_PROVIDER=ollama` and `OLLAMA_MODEL=<model name>` |
| **Claude API** | `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=<key>` |

Then ask a question:

```bash
python pipeline.py query "What is our leave policy?"
```

If you don't have documents yet, try `sample_docs/` first.

## Reference modules

| Module | Use it for | Level |
|---|---|---|
| [`local-models`](local-models/) | Engine control, status checks, and prompt formats | Reference tool |
| [`languages`](languages/) | AI patterns across programming languages | Reference example |
| [`domains`](domains/) | Starting points for robotics, quantum computing, and cloud | Reference example |

## Configure models

Every module reads `.env` from the repo root. You can change model versions without editing code.

```env
CLAUDE_MODEL=claude-haiku-5-5
GEMINI_MODEL=gemini-3.5-flash
OLLAMA_MODEL=llama3.2
```

> [!WARNING]
> Don't commit `.env`, and don't expose `ai-api` to the internet without setting `APP_API_KEY`.

## Check and test

`hope.py` uses only the Python standard library. It needs no API key and no Docker.

```bash
python hope.py status
```

Shows what is installed, whether keys are set, and whether Ollama is running.

```bash
python hope.py list -v
```

Lists each blueprint with what has been tested and what has not (the data lives in [catalog.json](catalog.json)).

```bash
python hope.py check
```

Checks the catalog, links in the docs, and unit tests including Thai search. Run it before opening a pull request.

```bash
python hope.py test mock
```

Tests the agent, workflows, `llm-eval`, and `ai-api` against a mock Anthropic server. Run `npm ci --prefix ai-api` first. It does not judge the quality of real model answers.

## Contributing

You can fix broken commands, add blueprints, or propose a new field. See [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md). Those guides are currently in Thai.

## License

Code uses the [MIT License](LICENSE). Content uses [CC BY 4.0](LICENSE-CONTENT.md). Third-party files keep their original licenses.

## Author

**Daranpat Pattarakanpong (Shin)**
