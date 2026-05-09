import json


def _detect_by_content(content: str) -> str | None:
    stripped = content.strip()
    if not stripped:
        return None

    if stripped.startswith("<!DOCTYPE html") or stripped.startswith("<html"):
        return "html"

    if stripped.startswith("|") or stripped.startswith("|---"):
        return "markdown"

    lines = [l for l in stripped.split("\n") if l.strip()]
    if lines:
        header_count = sum(1 for l in lines[:20] if l.startswith("#"))
        if header_count >= 2 or (lines and lines[0].startswith("#")):
            return "markdown"

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return "json_array"
            if isinstance(parsed, dict):
                return "json_object"
        except json.JSONDecodeError:
            pass

    if "," in stripped and "\n" in stripped[:500]:
        first_line = stripped.split("\n")[0]
        if "," in first_line and len(first_line.split(",")) >= 2:
            return "csv"

    return None


def _detect_by_extension(filename: str) -> str | None:
    fn = filename.lower()
    ext_map = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".json": "json_array",
        ".csv": "csv",
        ".tsv": "csv",
        ".html": "html",
        ".htm": "html",
        ".txt": "plain_text",
        ".log": "plain_text",
        ".yaml": "plain_text",
        ".yml": "plain_text",
        ".xml": "plain_text",
    }
    for ext, dtype in ext_map.items():
        if fn.endswith(ext):
            return dtype
    return None


def detect_doc_type(filename: str, content: str) -> str:
    detected = _detect_by_content(content)
    if detected:
        return detected
    detected = _detect_by_extension(filename)
    if detected:
        return detected
    return "plain_text"
