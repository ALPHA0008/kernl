from langgraph.graph import StateGraph, END
from langgraph.types import Send
from backend.graph.state import BrainState
from backend.graph.nodes.load_sources import load_sources
from backend.graph.nodes.chunk_documents import chunk_documents
from backend.graph.nodes.extract_decisions import extract_decisions
from backend.graph.nodes.extract_workflows import extract_workflows
from backend.graph.nodes.extract_exceptions import extract_exceptions
from backend.graph.nodes.detect_contradictions import detect_contradictions
from backend.graph.nodes.synthesize_skills import synthesize_skills
from backend.graph.nodes.link_evidence import link_evidence
from backend.graph.nodes.score_confidence import score_confidence
from backend.graph.nodes.write_brain import write_brain


def route_to_extraction(state: BrainState) -> list[Send]:
    return [
        Send("extract_decisions", dict(state)),
        Send("extract_workflows", dict(state)),
        Send("extract_exceptions", dict(state)),
        Send("detect_contradictions", dict(state)),
    ]


def build_compilation_graph() -> StateGraph:
    """
    load_sources → chunk_documents → route_to_extraction (Send fan-out)
    → [extract_decisions, extract_workflows, extract_exceptions, detect_contradictions] (parallel)
    → synthesize_skills → link_evidence → score_confidence → write_brain
    """
    workflow = StateGraph(BrainState)

    workflow.add_node("load_sources", load_sources)
    workflow.add_node("chunk_documents", chunk_documents)

    workflow.add_node("extract_decisions", extract_decisions)
    workflow.add_node("extract_workflows", extract_workflows)
    workflow.add_node("extract_exceptions", extract_exceptions)
    workflow.add_node("detect_contradictions", detect_contradictions)

    workflow.add_node("synthesize_skills", synthesize_skills)
    workflow.add_node("link_evidence", link_evidence)
    workflow.add_node("score_confidence", score_confidence)
    workflow.add_node("write_brain", write_brain)

    workflow.set_entry_point("load_sources")
    workflow.add_edge("load_sources", "chunk_documents")

    workflow.add_conditional_edges(
        "chunk_documents",
        route_to_extraction,
        [
            "extract_decisions",
            "extract_workflows",
            "extract_exceptions",
            "detect_contradictions",
        ],
    )

    workflow.add_edge("extract_decisions", "synthesize_skills")
    workflow.add_edge("extract_workflows", "synthesize_skills")
    workflow.add_edge("extract_exceptions", "synthesize_skills")
    workflow.add_edge("detect_contradictions", "synthesize_skills")

    workflow.add_edge("synthesize_skills", "link_evidence")
    workflow.add_edge("link_evidence", "score_confidence")
    workflow.add_edge("score_confidence", "write_brain")
    workflow.add_edge("write_brain", END)

    return workflow.compile()
