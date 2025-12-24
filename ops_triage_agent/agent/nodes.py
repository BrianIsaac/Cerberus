"""LangGraph workflow nodes for the ops assistant."""

import json
from datetime import datetime
from typing import Any

import structlog
from ddtrace import tracer
from ddtrace.llmobs import LLMObs
from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions
from langgraph.types import interrupt

from ops_triage_agent.agent.state import (
    AgentState,
    CollectedEvidence,
    Hypothesis,
    IntentType,
    ProposedAction,
    WorkflowStage,
)
from ops_triage_agent.config import settings
from ops_triage_agent.mcp_client.client import DatadogMCPClient
from ops_triage_agent.observability import (
    emit_budget_exceeded,
    emit_escalation,
    emit_quality_metric,
    emit_review_outcome,
)
from ops_triage_agent.prompts.intake_v1 import (
    CLARIFICATION_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    INTAKE_USER_TEMPLATE,
)
from ops_triage_agent.prompts.synthesis_v1 import (
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)
from ops_triage_agent.security import validate_input

logger = structlog.get_logger()

# Try to import RAGAS for quality evaluation
try:
    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import answer_relevancy, faithfulness

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.info("ragas_not_available", message="RAGAS library not installed")


def get_genai_client() -> genai.Client:
    """Get configured Google GenAI client for Vertex AI.

    Returns:
        Configured genai.Client instance
    """
    return genai.Client(
        http_options=HttpOptions(api_version="v1"),
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


def _set_span_tags(state: AgentState) -> None:
    """Set common span tags for observability.

    Args:
        state: Current workflow state
    """
    span = tracer.current_span()
    if span:
        service = state.get("extracted_service") or state.get("service", "unknown")
        span.set_tag("service_name", service)
        span.set_tag("env", state.get("environment", "production"))
        span.set_tag("time_window", state.get("time_window", "last_15m"))
        span.set_tag("prompt_version", "v1")
        span.set_tag("model", settings.gemini_model)


def intake_node(state: AgentState) -> dict[str, Any]:
    """Intake node: classify intent and extract parameters.

    Args:
        state: Current workflow state

    Returns:
        State updates for intake stage
    """
    with LLMObs.agent(name="agent.intake"):
        _set_span_tags(state)
        logger.info("intake_node_executing", query=state["user_query"][:100])

        # Security validation: check for prompt injection and PII
        is_valid, error_message = validate_input(state["user_query"])
        if not is_valid:
            logger.warning("security_validation_failed", error=error_message)
            emit_escalation(f"security_validation_failed: {error_message}")
            return {
                "stage": WorkflowStage.ESCALATED,
                "escalation_reason": f"Security validation failed: {error_message}",
                "step_count": state["step_count"] + 1,
                "messages": [f"Security validation failed: {error_message}"],
                "final_response": {
                    "status": "escalated",
                    "reason": f"Security validation failed: {error_message}",
                },
            }

        client = get_genai_client()

        # Build prompt
        prompt = INTAKE_USER_TEMPLATE.format(
            user_query=state["user_query"],
            service=state["service"] or "not specified",
            time_window=state["time_window"],
        )

        # Call Gemini for intent classification
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=INTAKE_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        # Parse response
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("intake_parse_failed", response=response.text[:200])
            result = {
                "intent": "clarification_needed",
                "service": None,
                "time_window": "last_15m",
                "confidence": 0.0,
            }

        intent = IntentType(result.get("intent", "clarification_needed"))
        confidence = result.get("confidence", 0.0)

        # Emit quality metric
        emit_quality_metric("intake_confidence", confidence)

        logger.info(
            "intake_completed",
            intent=intent.value,
            confidence=confidence,
            service=result.get("service"),
        )

        return {
            "stage": WorkflowStage.INTAKE,
            "intent": intent,
            "extracted_service": result.get("service"),
            "extracted_time_window": result.get("time_window", "last_15m"),
            "intake_confidence": confidence,
            "model_calls": state["model_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "messages": [
                f"Intake: classified as {intent.value} with confidence {confidence:.2f}"
            ],
        }


def intake_router(state: AgentState) -> str:
    """Route after intake based on intent and confidence.

    Args:
        state: Current workflow state

    Returns:
        Next node name: "clarification", "escalate", or "collect"
    """
    intent = state["intent"]
    confidence = state["intake_confidence"]
    service = state["extracted_service"] or state["service"]

    # Check budgets
    if state["step_count"] >= settings.agent_max_steps:
        emit_budget_exceeded("steps", settings.agent_max_steps, state["step_count"])
        return "escalate"

    if state["model_calls"] >= settings.agent_max_model_calls:
        emit_budget_exceeded(
            "model_calls", settings.agent_max_model_calls, state["model_calls"]
        )
        return "escalate"

    if state["tool_calls"] >= settings.agent_max_tool_calls:
        emit_budget_exceeded(
            "tool_calls", settings.agent_max_tool_calls, state["tool_calls"]
        )
        return "escalate"

    # Check if we need clarification
    if intent == IntentType.CLARIFICATION_NEEDED:
        if state["clarification_attempts"] < 2:
            return "clarification"
        else:
            return "escalate"

    # Check confidence threshold
    if confidence < settings.confidence_threshold:
        if state["clarification_attempts"] < 2:
            return "clarification"
        else:
            return "escalate"

    # Check if we have a service
    if not service:
        if state["clarification_attempts"] < 2:
            return "clarification"
        else:
            return "escalate"

    return "collect"


def clarification_node(state: AgentState) -> dict[str, Any]:
    """Request clarification from user via interrupt.

    Args:
        state: Current workflow state

    Returns:
        State updates with user's clarification response
    """
    with LLMObs.task(name="agent.clarification"):
        logger.info(
            "clarification_requested", attempts=state["clarification_attempts"]
        )

        # This will pause the graph and wait for user input
        user_response = interrupt(CLARIFICATION_PROMPT)

        # When resumed, update the query with clarification
        return {
            "user_query": f"{state['user_query']}\n\nClarification: {user_response}",
            "clarification_attempts": state["clarification_attempts"] + 1,
            "step_count": state["step_count"] + 1,
            "messages": [f"Clarification received: {user_response}"],
        }


def escalate_node(state: AgentState) -> dict[str, Any]:
    """Escalate to human when agent cannot proceed.

    Args:
        state: Current workflow state

    Returns:
        State updates for escalation
    """
    with LLMObs.task(name="agent.escalate"):
        reason = state.get("escalation_reason") or (
            "Unable to classify request with sufficient confidence after multiple attempts"
        )

        logger.info("escalating_to_human", reason=reason)
        emit_escalation(reason)

        return {
            "stage": WorkflowStage.ESCALATED,
            "escalation_reason": reason,
            "step_count": state["step_count"] + 1,
            "messages": [f"Escalated: {reason}"],
            "final_response": {
                "status": "escalated",
                "reason": reason,
                "partial_analysis": {
                    "query": state["user_query"],
                    "extracted_service": state["extracted_service"],
                    "confidence": state["intake_confidence"],
                },
            },
        }


async def collect_node(state: AgentState) -> dict[str, Any]:
    """Collect evidence from Datadog via MCP server.

    Uses MCP client to invoke tools - all calls are auto-instrumented by ddtrace.

    Args:
        state: Current workflow state

    Returns:
        State updates with collected evidence
    """
    with LLMObs.agent(name="agent.collect"):
        service = state["extracted_service"] or state["service"]
        time_window = state["extracted_time_window"] or state["time_window"]

        _set_span_tags(state)
        logger.info("collect_node_executing", service=service, time_window=time_window)

        collection_errors = []
        tool_calls = state["tool_calls"]

        metrics_data = None
        logs_data = None
        traces_data = None

        # Use MCP client for all Datadog tool calls
        async with DatadogMCPClient() as mcp:
            # Fetch metrics via MCP
            with LLMObs.task(name="agent.collect.metrics"):
                try:
                    metrics_data = await mcp.get_metrics(
                        service=service, time_window=time_window
                    )
                    tool_calls += 1
                except Exception as e:
                    logger.error("metrics_collection_failed", error=str(e))
                    collection_errors.append(f"Metrics: {str(e)}")

            # Search logs via MCP
            with LLMObs.task(name="agent.collect.logs"):
                try:
                    logs_data = await mcp.get_logs(
                        service=service,
                        query="status:error OR status:warn",
                        time_window=time_window,
                    )
                    tool_calls += 1
                except Exception as e:
                    logger.error("logs_collection_failed", error=str(e))
                    collection_errors.append(f"Logs: {str(e)}")

            # Search traces via MCP
            with LLMObs.task(name="agent.collect.traces"):
                try:
                    traces_data = await mcp.list_spans(
                        service=service,
                        query="status:error",
                        time_window=time_window,
                    )
                    tool_calls += 1
                except Exception as e:
                    logger.error("traces_collection_failed", error=str(e))
                    collection_errors.append(f"Traces: {str(e)}")

        evidence = CollectedEvidence(
            metrics=metrics_data,
            logs=logs_data,
            traces=traces_data,
            collection_errors=collection_errors,
        )

        logger.info(
            "collect_completed",
            has_metrics=metrics_data is not None,
            has_logs=logs_data is not None,
            has_traces=traces_data is not None,
            errors=len(collection_errors),
        )

        return {
            "stage": WorkflowStage.COLLECT,
            "evidence": evidence,
            "tool_calls": tool_calls,
            "step_count": state["step_count"] + 1,
            "messages": [
                f"Collected evidence: {3 - len(collection_errors)}/3 sources successful"
            ],
        }


def collect_router(state: AgentState) -> str:
    """Route after collection based on evidence quality.

    Args:
        state: Current workflow state

    Returns:
        Next node name: "synthesis" or "escalate"
    """
    evidence = state["evidence"]

    # Check if we have any evidence
    if not evidence:
        return "escalate"

    # Check if all sources failed
    if not evidence.metrics and not evidence.logs and not evidence.traces:
        return "escalate"

    # Check budget
    if state["step_count"] >= settings.agent_max_steps - 2:
        emit_budget_exceeded("steps", settings.agent_max_steps, state["step_count"])
        return "escalate"

    return "synthesis"


def synthesis_node(state: AgentState) -> dict[str, Any]:
    """Synthesise hypotheses from collected evidence.

    Args:
        state: Current workflow state

    Returns:
        State updates with synthesis results
    """
    with LLMObs.agent(name="agent.synthesise"):
        service = state["extracted_service"] or state["service"]
        time_window = state["extracted_time_window"] or state["time_window"]
        evidence = state["evidence"]

        _set_span_tags(state)
        logger.info("synthesis_node_executing", service=service)

        client = get_genai_client()

        # Format evidence for prompt
        metrics_str = (
            json.dumps(evidence.metrics, indent=2)
            if evidence.metrics
            else "No metrics data"
        )
        logs_str = (
            json.dumps(evidence.logs, indent=2, default=str)
            if evidence.logs
            else "No logs data"
        )
        traces_str = (
            json.dumps(evidence.traces, indent=2)
            if evidence.traces
            else "No traces data"
        )

        prompt = SYNTHESIS_USER_TEMPLATE.format(
            service=service,
            time_window=time_window,
            metrics_data=metrics_str[:3000],  # Truncate to avoid token limits
            logs_data=logs_str[:3000],
            traces_data=traces_str[:2000],
            user_query=state["user_query"],
        )

        # Build context for RAGAS evaluation
        context = f"""Metrics: {metrics_str[:1000]}
Logs: {logs_str[:1000]}
Traces: {traces_str[:1000]}"""

        # Call Gemini for synthesis
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )

        # Parse response
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("synthesis_parse_failed", response=response.text[:200])
            result = {
                "summary": "Unable to parse synthesis response",
                "hypotheses": [],
                "next_steps": [],
                "overall_confidence": 0.0,
                "requires_incident": False,
            }

        # Build hypothesis objects
        hypotheses = []
        for h in result.get("hypotheses", []):
            hypotheses.append(
                Hypothesis(
                    rank=h.get("rank", len(hypotheses) + 1),
                    description=h.get("description", ""),
                    confidence=h.get("confidence", 0.0),
                    evidence=h.get("evidence", []),
                    query_links=h.get("query_links", []),
                )
            )

        confidence = result.get("overall_confidence", 0.0)
        requires_incident = result.get("requires_incident", False)

        # Emit quality metrics
        emit_quality_metric("synthesis_confidence", confidence)

        # Run RAGAS evaluation on the synthesis if available
        if RAGAS_AVAILABLE:
            try:
                answer = result.get("summary", "")
                eval_data = {
                    "question": [state["user_query"]],
                    "answer": [answer],
                    "contexts": [[context]],
                }
                dataset = Dataset.from_dict(eval_data)

                ragas_results = ragas_evaluate(
                    dataset,
                    metrics=[faithfulness, answer_relevancy],
                )

                faithfulness_score = ragas_results.get("faithfulness", 0.0)
                answer_relevancy_score = ragas_results.get("answer_relevancy", 0.0)

                logger.info(
                    "ragas_evaluation_completed",
                    faithfulness=faithfulness_score,
                    answer_relevancy=answer_relevancy_score,
                )

                emit_quality_metric("ragas_faithfulness", faithfulness_score)
                emit_quality_metric("ragas_answer_relevancy", answer_relevancy_score)

            except Exception as e:
                logger.error("ragas_evaluation_failed", error=str(e))
        else:
            logger.warning(
                "ragas_not_available",
                message="RAGAS evaluation skipped - library not installed",
            )

        # Check if intent suggests write action
        requires_approval = (
            state["intent"] == IntentType.WRITE_INTENT or requires_incident
        )

        logger.info(
            "synthesis_completed",
            hypothesis_count=len(hypotheses),
            confidence=confidence,
            requires_approval=requires_approval,
        )

        return {
            "stage": WorkflowStage.SYNTHESIS,
            "summary": result.get("summary", ""),
            "hypotheses": hypotheses,
            "next_steps": result.get("next_steps", []),
            "synthesis_confidence": confidence,
            "requires_approval": requires_approval,
            "model_calls": state["model_calls"] + 1,
            "step_count": state["step_count"] + 1,
            "messages": [
                f"Synthesis: {len(hypotheses)} hypotheses, confidence {confidence:.2f}"
            ],
        }


def synthesis_router(state: AgentState) -> str:
    """Route after synthesis based on confidence and intent.

    Args:
        state: Current workflow state

    Returns:
        Next node name: "approval", "escalate", or "complete"
    """
    confidence = state["synthesis_confidence"]

    # Check if escalation was triggered during synthesis
    if state.get("escalation_reason"):
        emit_escalation(state["escalation_reason"])
        return "escalate"

    # Check budgets
    if state["step_count"] >= settings.agent_max_steps:
        emit_budget_exceeded("steps", settings.agent_max_steps, state["step_count"])
        return "escalate"

    if state["model_calls"] >= settings.agent_max_model_calls:
        emit_budget_exceeded(
            "model_calls", settings.agent_max_model_calls, state["model_calls"]
        )
        return "escalate"

    if state["tool_calls"] >= settings.agent_max_tool_calls:
        emit_budget_exceeded(
            "tool_calls", settings.agent_max_tool_calls, state["tool_calls"]
        )
        return "escalate"

    # Check confidence threshold
    if confidence < settings.confidence_threshold:
        emit_escalation("low_synthesis_confidence")
        return "escalate"

    # Check if approval is needed
    if state["requires_approval"]:
        return "approval"

    return "complete"


def approval_node(state: AgentState) -> dict[str, Any]:
    """Request approval for write actions via interrupt.

    Args:
        state: Current workflow state

    Returns:
        State updates with approval decision
    """
    with LLMObs.task(name="agent.approval_gate"):
        _set_span_tags(state)
        logger.info("approval_requested")

        # Build proposed action
        service = state["extracted_service"] or state["service"]

        # Collect evidence links
        evidence_links = []
        if state["evidence"]:
            if state["evidence"].metrics:
                link = state["evidence"].metrics.get("dashboard_link", "")
                if link:
                    evidence_links.append(link)
            if state["evidence"].logs:
                link = state["evidence"].logs.get("logs_link", "")
                if link:
                    evidence_links.append(link)
            if state["evidence"].traces:
                link = state["evidence"].traces.get("traces_link", "")
                if link:
                    evidence_links.append(link)

        proposed = ProposedAction(
            action_type="case",  # Default to case, can be incident for high severity
            title=f"Triage: {service} - {state['summary'][:50] if state['summary'] else 'Unknown'}",
            description=state["summary"] or "",
            severity="SEV-3",  # Default
            evidence_links=evidence_links,
            hypotheses=[h.description for h in state["hypotheses"]],
            next_steps=state["next_steps"],
        )

        # Format approval request
        approval_message = f"""
Proposed Action: Create {proposed.action_type.upper()}

Title: {proposed.title}
Description: {proposed.description}

Hypotheses:
{chr(10).join(f'  {i+1}. {h}' for i, h in enumerate(proposed.hypotheses))}

Next Steps:
{chr(10).join(f'  - {s}' for s in proposed.next_steps)}

Enter 'approve' to create, 'reject' to cancel, or 'edit' to modify:
"""

        # Interrupt for human decision
        decision = interrupt(approval_message)

        # Emit metric for human verification signal capture
        outcome = decision.strip().lower() if decision else "rejected"
        emit_review_outcome(outcome)

        return {
            "stage": WorkflowStage.APPROVAL,
            "proposed_action": proposed,
            "approval_decision": decision,
            "approval_status": outcome,
            "step_count": state["step_count"] + 1,
            "messages": [f"Approval decision: {decision}"],
        }


def approval_router(state: AgentState) -> str:
    """Route based on approval decision.

    Args:
        state: Current workflow state

    Returns:
        Next node name: "writeback" or "complete"
    """
    status = state["approval_status"]

    if status == "approved" or status == "approve":
        return "writeback"
    elif status == "edit":
        # For now, treat edit as approve (could add edit flow)
        return "writeback"
    else:
        return "complete"


async def writeback_node(state: AgentState) -> dict[str, Any]:
    """Create incident or case in Datadog via MCP.

    Args:
        state: Current workflow state

    Returns:
        State updates with created incident/case IDs
    """
    with LLMObs.agent(name="agent.writeback"):
        proposed = state["proposed_action"]

        logger.info("writeback_executing", action_type=proposed.action_type)

        try:
            async with DatadogMCPClient() as mcp:
                if proposed.action_type == "incident":
                    result = await mcp.create_incident(
                        title=proposed.title,
                        summary=proposed.description,
                        severity=proposed.severity,
                        evidence_links=proposed.evidence_links,
                        hypotheses=proposed.hypotheses,
                        next_steps=proposed.next_steps,
                    )

                    incident_id = result.get("incident_id")
                    if not incident_id:
                        raise ValueError(
                            "Incident creation failed: no incident_id returned"
                        )

                    # Log complete interaction for compliance audit
                    logger.info(
                        "audit_trail",
                        event_type="writeback_complete",
                        trace_id=state.get("trace_id"),
                        user_query=state.get("user_query"),
                        hypotheses_count=len(state.get("hypotheses", [])),
                        approval_decision=state.get("approval_decision"),
                        incident_id=incident_id,
                        action_type="incident",
                        created_at=datetime.utcnow().isoformat(),
                    )

                    return {
                        "stage": WorkflowStage.WRITEBACK,
                        "incident_id": incident_id,
                        "tool_calls": state["tool_calls"] + 1,
                        "step_count": state["step_count"] + 1,
                        "messages": [f"Created incident: {incident_id}"],
                    }
                else:
                    result = await mcp.create_case(
                        title=proposed.title,
                        description=proposed.description,
                        priority=proposed.severity.replace("SEV-", "P"),
                        evidence_links=proposed.evidence_links,
                        hypotheses=proposed.hypotheses,
                        next_steps=proposed.next_steps,
                    )

                    case_id = result.get("case_id")
                    if not case_id:
                        raise ValueError("Case creation failed: no case_id returned")

                    # Log complete interaction for compliance audit
                    logger.info(
                        "audit_trail",
                        event_type="writeback_complete",
                        trace_id=state.get("trace_id"),
                        user_query=state.get("user_query"),
                        hypotheses_count=len(state.get("hypotheses", [])),
                        approval_decision=state.get("approval_decision"),
                        case_id=case_id,
                        action_type="case",
                        created_at=datetime.utcnow().isoformat(),
                    )

                    return {
                        "stage": WorkflowStage.WRITEBACK,
                        "case_id": case_id,
                        "tool_calls": state["tool_calls"] + 1,
                        "step_count": state["step_count"] + 1,
                        "messages": [f"Created case: {case_id}"],
                    }
        except Exception as e:
            logger.error("writeback_failed", error=str(e))
            return {
                "stage": WorkflowStage.WRITEBACK,
                "error": str(e),
                "step_count": state["step_count"] + 1,
                "messages": [f"Writeback failed: {str(e)}"],
            }


def complete_node(state: AgentState) -> dict[str, Any]:
    """Finalise the workflow and build response.

    Args:
        state: Current workflow state

    Returns:
        State updates with final response
    """
    with LLMObs.task(name="agent.complete"):
        logger.info("workflow_completing")

        # Build final response
        response = {
            "status": "completed",
            "summary": state["summary"],
            "hypotheses": [
                {
                    "rank": h.rank,
                    "description": h.description,
                    "confidence": h.confidence,
                    "evidence": h.evidence,
                }
                for h in state["hypotheses"]
            ],
            "next_steps": state["next_steps"],
            "confidence": state["synthesis_confidence"],
            "step_count": state["step_count"],
            "tool_calls": state["tool_calls"],
            "model_calls": state["model_calls"],
        }

        # Add incident/case info if created
        if state.get("incident_id"):
            response["incident_id"] = state["incident_id"]
            response["incident_link"] = (
                f"https://app.{settings.dd_site}/incidents/{state['incident_id']}"
            )

        if state.get("case_id"):
            response["case_id"] = state["case_id"]
            response["case_link"] = (
                f"https://app.{settings.dd_site}/cases/{state['case_id']}"
            )

        return {
            "stage": WorkflowStage.COMPLETE,
            "final_response": response,
            "messages": ["Workflow completed"],
        }
