from langgraph.graph import END, START, StateGraph

from app.workflows.nodes import make_nodes
from app.workflows.state import ChatGraphState


def build_chat_graph(model, retriever):
    retrieve, route, rewrite, generate, insufficient, propose = make_nodes(model, retriever)
    graph = StateGraph(ChatGraphState)
    graph.add_node("retrieve_context", retrieve)
    graph.add_node("rewrite_query", rewrite)
    graph.add_node("generate_answer", generate)
    graph.add_node("generate_insufficient_answer", insufficient)
    graph.add_node("propose_memories", propose)
    graph.add_edge(START, "retrieve_context")
    graph.add_conditional_edges("retrieve_context", route, {
        "generate": "generate_answer", "retry": "rewrite_query", "insufficient": "generate_insufficient_answer"
    })
    graph.add_edge("rewrite_query", "retrieve_context")
    graph.add_edge("generate_answer", "propose_memories")
    graph.add_edge("generate_insufficient_answer", "propose_memories")
    graph.add_edge("propose_memories", END)
    return graph.compile()
