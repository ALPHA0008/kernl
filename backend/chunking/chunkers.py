import json
import csv
import io
import re


DEFAULT_CHUNK_SIZE = 2000
DEFAULT_OVERLAP = 200


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _recursive_split(
    text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    separators = ["\n\n", "\n", ". ", " "]
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size * 4, len(text))
        if end < len(text):
            best_sep = -1
            for sep in separators:
                pos = text.rfind(sep, start, end)
                if pos > best_sep:
                    best_sep = pos
            if best_sep > start:
                end = best_sep + len(sep) if best_sep >= 0 else end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap * 4 if end < len(text) else len(text)

    return chunks if chunks else [text.strip()]


def chunk_markdown(
    content: str, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> list[dict]:
    lines = content.split("\n")
    sections = []
    current_header = "Introduction"
    current_body = []
    current_level = 0

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            if current_body:
                sections.append((current_header, "\n".join(current_body).strip()))
            current_level = len(header_match.group(1))
            current_header = header_match.group(2).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        sections.append((current_header, "\n".join(current_body).strip()))

    chunks = []
    for i, (header, body) in enumerate(sections):
        if not body:
            continue
        text = f"[{header}] {body}"
        if _estimate_tokens(text) > chunk_size:
            sub_chunks = _recursive_split(body, chunk_size)
            for j, sub in enumerate(sub_chunks):
                chunks.append(
                    {
                        "text": f"[{header}] {sub}",
                        "source_file": filename,
                        "chunk_index": i * 1000 + j,
                        "doc_type": "markdown",
                        "section_header": header,
                    }
                )
        else:
            chunks.append(
                {
                    "text": text,
                    "source_file": filename,
                    "chunk_index": i,
                    "doc_type": "markdown",
                    "section_header": header,
                }
            )

    return chunks


def chunk_json_array(
    content: str, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> list[dict]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return [
            {
                "text": content,
                "source_file": filename,
                "chunk_index": 0,
                "doc_type": "json_array",
            }
        ]

    if not isinstance(data, list):
        text = json.dumps(data, indent=2)
        return [
            {
                "text": text,
                "source_file": filename,
                "chunk_index": 0,
                "doc_type": "json_object",
            }
        ]

    chunks = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            parts = []
            for key in (
                "text",
                "message",
                "content",
                "subject",
                "description",
                "resolution",
                "body",
            ):
                if item.get(key):
                    parts.append(f"{key}: {item[key]}")
            for key in (
                "user",
                "author",
                "channel",
                "priority",
                "customer_plan",
                "status",
            ):
                if item.get(key):
                    parts.append(f"{key}: {item[key]}")
            text = " | ".join(parts)
            if not text:
                text = json.dumps(item)
        elif isinstance(item, str):
            text = item
        else:
            text = json.dumps(item)

        if text:
            chunks.append(
                {
                    "text": text,
                    "source_file": filename,
                    "chunk_index": i,
                    "doc_type": "json_array",
                }
            )

    return chunks


def chunk_csv(
    content: str, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return [
            {
                "text": content,
                "source_file": filename,
                "chunk_index": 0,
                "doc_type": "csv",
            }
        ]

    headers = reader.fieldnames
    rows = list(reader)
    if not rows:
        return []

    chunks = []
    batch = []
    batch_text = ""

    for i, row in enumerate(rows):
        row_parts = [f"{k}: {v}" for k, v in row.items() if v]
        row_str = " | ".join(row_parts)
        if _estimate_tokens(batch_text + "\n" + row_str) > chunk_size and batch:
            chunks.append(
                {
                    "text": batch_text,
                    "source_file": filename,
                    "chunk_index": len(chunks),
                    "doc_type": "csv",
                }
            )
            batch = [row]
            batch_text = row_str
        else:
            if batch_text:
                batch_text += "\n"
            batch_text += row_str
            batch.append(row)

    if batch:
        chunks.append(
            {
                "text": batch_text,
                "source_file": filename,
                "chunk_index": len(chunks),
                "doc_type": "csv",
            }
        )

    return chunks


def chunk_html(
    content: str, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> list[dict]:
    text = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    sections = re.split(r"\n\s*(?=(?:##|###|####|h[1-6]))", text)
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        if _estimate_tokens(section) > chunk_size:
            subs = _recursive_split(section, chunk_size)
            for j, sub in enumerate(subs):
                chunks.append(
                    {
                        "text": sub,
                        "source_file": filename,
                        "chunk_index": i * 1000 + j,
                        "doc_type": "html",
                    }
                )
        else:
            chunks.append(
                {
                    "text": section,
                    "source_file": filename,
                    "chunk_index": i,
                    "doc_type": "html",
                }
            )

    return (
        chunks
        if chunks
        else [
            {
                "text": text[: chunk_size * 4],
                "source_file": filename,
                "chunk_index": 0,
                "doc_type": "html",
            }
        ]
    )


def chunk_plain_text(
    content: str,
    filename: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict]:
    parts = _recursive_split(content, chunk_size, overlap)
    return [
        {
            "text": part,
            "source_file": filename,
            "chunk_index": i,
            "doc_type": "plain_text",
        }
        for i, part in enumerate(parts)
    ]


CHUNKERS = {
    "markdown": chunk_markdown,
    "json_array": chunk_json_array,
    "json_object": chunk_json_array,
    "csv": chunk_csv,
    "html": chunk_html,
    "plain_text": chunk_plain_text,
}


def get_chunker(doc_type: str):
    return CHUNKERS.get(doc_type, chunk_plain_text)
