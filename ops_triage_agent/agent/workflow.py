"""LangGraph workflow definition for the ops assistant."""

import structlog
from ddtrace.llmobs.decorators import workflow as llmobs_workflow
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    approval_node,
    approval_router,
    clarification_node,
    collect_node,
    collect_router,
    complete_node,
    escalate_node,
    intake_node,
    intake_router,
    synthesis_node,
    synthesis_router,
    writeback_node,
)
from app.agent.state import AgentState, create_initial_state
from app.config import settings

logger = structlog.get_logger()


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow for ops assistant.

    Returns:
        Configured StateGraph builder
    """
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("intake", intake_node)
    builder.add_node("clarification", clarification_node)
    builder.add_node("escalate", escalate_node)
    builder.add_node("collect", collect_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("approval", approval_node)
    builder.add_node("writeback", writeback_node)
    builder.add_node("complete", complete_node)

    # Add edges
    builder.add_edge(START, "intake")

    # Intake routing
    builder.add_conditional_edges(
        "intake",
        intake_router,
        {
            "clarification": "clarification",
            "escalate": "escalate",
            "collect": "collect",
        },
    )

    # Clarification loops back to intake
    builder.add_edge("clarification", "intake")

    # Escalate ends the workflow
    builder.add_edge("escalate", END)

    # Collect routing
    builder.add_conditional_edges(
        "collect",
        collect_router,
        {
            "synthesis": "synthesis",
            "escalate": "escalate",
        },
    )

    # Synthesis routing
    builder.add_conditional_edges(
        "synthesis",
        synthesis_router,
        {
            "approval": "approval",
            "escalate": "escalate",
            "complete": "complete",
        },
    )

    # Approval routing
    builder.add_conditional_edges(
        "approval",
        approval_router,
        {
            "writeback": "writeback",
            "complete": "complete",
        },
    )

    # Writeback goes to complete
    builder.add_edge("writeback", "complete")

    # Complete ends the workflow
    builder.add_edge("complete", END)

    return builder


# Global workflow instance with checkpointing
_checkpointer = MemorySaver()
_workflow_builder = build_workflow()
workflow_graph = _workflow_builder.compile(
    checkpointer=_checkpointer,
)


@llmobs_workflow
async def run_triage_workflow(
    user_query: str,
    service: str | None = None,
    environment: str = "production",
    time_window: str = "last_15m",
    thread_id: str | None = None,
) -> dict:
    """Run the triage workflow.

    Args:
        user_query: User's triage question
        service: Optional service name
        environment: Target environment
        time_window: Time window for queries
        thread_id: Optional thread ID for resuming

    Returns:
        Final workflow response
    """
    logger.info(
        "workflow_starting",
        query=user_query[:100],
        service=service,
    )

    # Create initial state
    initial_state = create_initial_state(
        user_query=user_query,
        service=service,
        environment=environment,
        time_window=time_window,
    )

    # Configure thread for checkpointing
    config = {
        "configurable": {
            "thread_id": thread_id or f"triage-{hash(user_query)}",
        },
        "recursion_limit": settings.agent_max_steps + 2,
    }

    # Run workflow
    final_state = None
    async for event in workflow_graph.astream(initial_state, config):
        # Extract the state from the event
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                final_state = node_output
                logger.debug("workflow_step", node=node_name, stage=node_output.get("stage"))

    if not final_state:
        raise RuntimeError("Workflow completed without final state")

    # Get response
    if final_state.get("final_response"):
        return final_state["final_response"]
    elif final_state.get("escalation_reason"):
        return {
            "status": "escalated",
            "reason": final_state["escalation_reason"],
        }
    else:
        return {
            "status": "error",
            "error": final_state.get("error", "Unknown error"),
        }


async def resume_workflow(
    thread_id: str,
    user_input: str | None = None,
) -> dict:
    """Resume a paused workflow with user input.

    Used to continue workflows that were interrupted (e.g., at approval gate).

    Args:
        thread_id: Thread ID of the workflow to resume
        user_input: User's input to continue the workflow

    Returns:
        Workflow response after resumption
    """
    logger.info(
        "workflow_resuming",
        thread_id=thread_id,
        has_input=user_input is not None,
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": settings.agent_max_steps + 2,
    }

    # Resume with user input
    final_state = None
    async for event in workflow_graph.astream(user_input, config):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                final_state = node_output
                logger.debug("workflow_step", node=node_name, stage=node_output.get("stage"))

    if not final_state:
        raise RuntimeError("Workflow resumed without final state")

    # Get response
    if final_state.get("final_response"):
        return final_state["final_response"]
    elif final_state.get("escalation_reason"):
        return {
            "status": "escalated",
            "reason": final_state["escalation_reason"],
        }
    else:
        return {
            "status": "error",
            "error": final_state.get("error", "Unknown error"),
        }
