from langgraph.graph import StateGraph, END
from backend.graph.state import BrainState
from backend.graph.nodes.load_and_chunk import load_and_chunk
from backend.graph.nodes.cluster_evidence import cluster_evidence
from backend.graph.nodes.synthesize_skills import synthesize_skills
from backend.graph.nodes.quality_normalize import quality_normalize
from backend.graph.nodes.write_brain import write_brain


def build_compilation_graph() -> StateGraph:
    """
    Linear 5-node pipeline:
      load_and_chunk → cluster_evidence → synthesize_skills → quality_normalize → write_brain
    """
    workflow = StateGraph(BrainState)

    workflow.add_node("load_and_chunk", load_and_chunk)
    workflow.add_node("cluster_evidence", cluster_evidence)
    workflow.add_node("synthesize_skills", synthesize_skills)
    workflow.add_node("quality_normalize", quality_normalize)
    workflow.add_node("write_brain", write_brain)

    workflow.set_entry_point("load_and_chunk")
    workflow.add_edge("load_and_chunk", "cluster_evidence")
    workflow.add_edge("cluster_evidence", "synthesize_skills")
    workflow.add_edge("synthesize_skills", "quality_normalize")
    workflow.add_edge("quality_normalize", "write_brain")
    workflow.add_edge("write_brain", END)

    return workflow.compile()
