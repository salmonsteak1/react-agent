"""Surface chat agent graph for LangGraph Platform.

Exports a top-level `graph` without custom checkpointing. Platform manages threads.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from chat_agents.agents.surface_chat_agent_v1 import SurfaceChatAgentV1


# Export a top-level compiled graph for LangGraph Platform.
# Platform supplies thread management and persistence; no custom checkpointer is used here.
_agent = SurfaceChatAgentV1()

if _agent.PROVIDER != "openai":
    raise ValueError(f"Unsupported provider: {_agent.PROVIDER}")

# Depends on OPENAI_API_KEY in the environment.
_llm = ChatOpenAI(model=_agent.MODEL, output_version="responses/v1")

# This is the object LangGraph Platform will import.
graph = create_react_agent(
    _llm,
    tools=_agent.TOOLS,
    prompt=_agent.INSTRUCTIONS,
)
