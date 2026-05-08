from langgraph.graph import StateGraph, END
from langgraph.types import Send
from backend.graph.state import BrainState
from backend.graph.nodes.load_sources import load_sources
from backend.graph.nodes.ingest_notion import ingest_notion
from backend.graph.nodes.ingest_slack import ingest_slack
from backend.graph.nodes.ingest_tickets import ingest_tickets
from backend.graph.nodes.ingest_join import ingest_join
from backend.graph.nodes.extract_decisions import extract_decisions
from backend.graph.nodes.extract_workflows import extract_workflows
from backend.graph.nodes.extract_exceptions import extract_exceptions
from backend.graph.nodes.detect_contradictions import detect_contradictions
from backend.graph.nodes.synthesize_skills import synthesize_skills
from backend.graph.nodes.link_evidence import link_evidence
from backend.graph.nodes.score_confidence import score_confidence
from backend.graph.nodes.write_brain import write_brain


def route_to_ingestion(state: BrainState) -> list[Send]:
    """Fan-out: dispatch source files to type-specific ingestion nodes."""
    sends = []
    for f in state.get("source_files", []):
        dt = f.get("doc_type", "unknown")
        payload = {
            "company_id": state["company_id"],
            "job_id": state["job_id"],
            "source_files": [f],
        }
        if dt == "notion_md":
            sends.append(Send("ingest_notion", payload))
        elif dt == "slack_json":
            sends.append(Send("ingest_slack", payload))
        elif dt == "tickets_json":
            sends.append(Send("ingest_tickets", payload))
    return sends


def route_to_extraction(state: BrainState) -> list[Send]:
    """Fan-out: dispatch all chunks to 4 parallel extraction agents."""
    return [
        Send("extract_decisions", dict(state)),
        Send("extract_workflows", dict(state)),
        Send("extract_exceptions", dict(state)),
        Send("detect_contradictions", dict(state)),
    ]


def build_compilation_graph() -> StateGraph:
    """
    Parallel multi-agent graph:

    load_sources
      → route_to_ingestion (Send fan-out)
      → [ingest_notion, ingest_slack, ingest_tickets] (parallel)
      → ingest_join (barrier)
      → route_to_extraction (Send fan-out)
      → [extract_decisions, extract_workflows, extract_exceptions, detect_contradictions] (parallel)
      → synthesize_skills → link_evidence → score_confidence → write_brain
    """
    workflow = StateGraph(BrainState)

    # --- Ingestion layer ---
    workflow.add_node("load_sources", load_sources)
    workflow.add_node("ingest_notion", ingest_notion)
    workflow.add_node("ingest_slack", ingest_slack)
    workflow.add_node("ingest_tickets", ingest_tickets)
    workflow.add_node("ingest_join", ingest_join)

    # --- Extraction layer ---
    workflow.add_node("extract_decisions", extract_decisions)
    workflow.add_node("extract_workflows", extract_workflows)
    workflow.add_node("extract_exceptions", extract_exceptions)
    workflow.add_node("detect_contradictions", detect_contradictions)

    # --- Compilation layer ---
    workflow.add_node("synthesize_skills", synthesize_skills)
    workflow.add_node("link_evidence", link_evidence)
    workflow.add_node("score_confidence", score_confidence)
    workflow.add_node("write_brain", write_brain)

    # --- Edges ---
    workflow.set_entry_point("load_sources")

    # load_sources fans out to 3 parallel ingest nodes
    workflow.add_conditional_edges(
        "load_sources",
        route_to_ingestion,
        [
            "ingest_notion",
            "ingest_slack",
            "ingest_tickets",
        ],
    )

    # All 3 ingest nodes converge at the barrier join
    workflow.add_edge("ingest_notion", "ingest_join")
    workflow.add_edge("ingest_slack", "ingest_join")
    workflow.add_edge("ingest_tickets", "ingest_join")

    # ingest_join fans out to 4 parallel extraction agents
    workflow.add_conditional_edges(
        "ingest_join",
        route_to_extraction,
        [
            "extract_decisions",
            "extract_workflows",
            "extract_exceptions",
            "detect_contradictions",
        ],
    )

    # All 4 extraction agents converge at synthesize_skills
    workflow.add_edge("extract_decisions", "synthesize_skills")
    workflow.add_edge("extract_workflows", "synthesize_skills")
    workflow.add_edge("extract_exceptions", "synthesize_skills")
    workflow.add_edge("detect_contradictions", "synthesize_skills")

    # Sequential compilation pipeline
    workflow.add_edge("synthesize_skills", "link_evidence")
    workflow.add_edge("link_evidence", "score_confidence")
    workflow.add_edge("score_confidence", "write_brain")
    workflow.add_edge("write_brain", END)

    return workflow.compile()
