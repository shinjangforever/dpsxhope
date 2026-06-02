"""tool: text_search — ค้นหา keyword ใน local text files"""
from pathlib import Path


def text_search(query: str, directory: str = ".", max_results: int = 5) -> dict:
    """ค้นหา query ใน .txt files ภายใน directory"""
    results = []
    for path in Path(directory).rglob("*.txt"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if query.lower() in text.lower():
            # ดึง snippet รอบๆ คำที่เจอ
            idx = text.lower().find(query.lower())
            start = max(0, idx - 100)
            end = min(len(text), idx + 200)
            results.append({
                "file": str(path),
                "snippet": text[start:end].strip(),
            })
        if len(results) >= max_results:
            break

    return {
        "query": query,
        "found": len(results),
        "results": results,
    }


TOOL_SCHEMA = {
    "name": "text_search",
    "description": "Search for a keyword or phrase in local text files.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword or phrase to search"},
            "directory": {"type": "string", "description": "Directory to search in", "default": "."},
        },
        "required": ["query"],
    },
}
