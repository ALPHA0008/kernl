import hashlib

MAX_CHUNK_CHARS = 12000

DECISION_KW = [
    "policy",
    "rule",
    "refund",
    "approve",
    "deny",
    "discount",
    "sop",
    "must",
    "shall",
    "eligible",
    "entitled",
    "require",
    "allowed",
    "forbidden",
]
WORKFLOW_KW = [
    "workflow",
    "process",
    "step",
    "procedure",
    "when",
    "then",
    "sequence",
    "phase",
    "first",
    "next",
    "finally",
]
EXCEPTION_KW = [
    "exception",
    "edge case",
    "but",
    "unless",
    "however",
    "never",
    "cannot",
    "only if",
    "special case",
    "no refund",
    "only",
]
CONTRADICTION_KW = [
    "vs",
    "disagree",
    "different",
    "actually",
    "but",
    "slack says",
    "however",
    "on the other hand",
    "conflict",
]
ENTITY_KW = [
    "role",
    "team",
    "department",
    "manager",
    "lead",
    "approver",
    "vendor",
    "customer",
    "plan",
    "tier",
    "sla",
    "invoice",
]


def _match_any(text: str, keywords: list) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def get_chunk_domains(text: str) -> list:
    matched = []
    if _match_any(text, DECISION_KW):
        matched.append("decisions")
    if _match_any(text, WORKFLOW_KW):
        matched.append("workflows")
    if _match_any(text, EXCEPTION_KW):
        matched.append("exceptions")
    if _match_any(text, CONTRADICTION_KW):
        matched.append("contradictions")
    if _match_any(text, ENTITY_KW):
        matched.append("entities")
    return (
        matched
        if matched
        else ["decisions", "workflows", "exceptions", "contradictions", "entities"]
    )


def batch_chunks(
    chunks: list[dict], max_chars: int = MAX_CHUNK_CHARS
) -> list[list[dict]]:
    current = []
    chars = 0
    out = []
    for c in chunks:
        text = c.get("text", "")
        if chars + len(text) > max_chars and current:
            out.append(current)
            current = []
            chars = 0
        current.append(c)
        chars += len(text)
    if current:
        out.append(current)
    return out if out else [chunks]


def chunks_to_text(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(c.get("text", "") for c in chunks)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
