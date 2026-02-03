"""
Voice Orchestrator Workflow: Transcript -> Action Plan.

Uses LangGraph for orchestration, reusing llm_utils.py for consistent
token tracking, cost estimation, and fallback behavior.

Pipeline: single node (build_plan) that converts transcript to VoicePlan JSON.
Does NOT execute tools -- only produces a plan for the execute endpoint.
"""
import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from mcp_server.server import TOOL_REGISTRY
from workflows.llm_utils import (
    get_llm_with_tracking,
    invoke_llm_with_metrics,
    parse_json_response,
    LLMMetrics,
)
from workflows.prompts.voice_prompts import (
    VOICE_PLAN_SYSTEM_PROMPT,
    VOICE_PLAN_USER_PROMPT,
    VOICE_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


class VoiceOrchestratorState(TypedDict):
    """State passed through the voice orchestrator workflow."""
    transcript: str
    plan: Optional[Dict[str, Any]]
    error: Optional[str]
    model_name: str
    llm_metrics: List[LLMMetrics]


def build_plan(state: VoiceOrchestratorState) -> VoiceOrchestratorState:
    """Node: LLM converts transcript to action plan JSON."""
    logger.info(f"VoiceOrchestrator: Processing transcript ({len(state['transcript'])} chars)")

    llm, model_name = get_llm_with_tracking()
    state["model_name"] = model_name or "none"

    if not llm:
        logger.warning("VoiceOrchestrator: No LLM API key configured")
        state["error"] = "No LLM API key configured"
        state["plan"] = {
            "intent": "unknown",
            "steps": [],
            "rationale": "No LLM available to parse intent.",
            "required_confirmations": [],
        }
        return state

    tool_descriptions = _build_tool_descriptions()
    system = VOICE_PLAN_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)
    user = VOICE_PLAN_USER_PROMPT.format(transcript=state["transcript"])
    full_prompt = f"{system}\n\n{user}"

    response = invoke_llm_with_metrics(llm, full_prompt, model_name)
    state["llm_metrics"].append(response.metrics)

    if response.success:
        parsed = parse_json_response(response.content)
        if parsed and "steps" in parsed:
            # Ensure required fields exist
            parsed.setdefault("intent", "unknown")
            parsed.setdefault("rationale", "")
            parsed.setdefault("required_confirmations", [])
            state["plan"] = parsed
            logger.info(f"VoiceOrchestrator: Plan built with {len(parsed['steps'])} steps")
            return state

    state["error"] = "Failed to parse LLM response into plan"
    state["plan"] = {
        "intent": "unknown",
        "steps": [],
        "rationale": "Could not parse instructor intent.",
        "required_confirmations": [],
    }
    return state


def _build_tool_descriptions() -> str:
    lines = []
    for name, entry in TOOL_REGISTRY.items():
        params = entry.get("parameters", {})
        properties = params.get("properties", {})
        required = set(params.get("required", []))
        fields = []
        for field_name, field_info in properties.items():
            type_name = field_info.get("type", "any")
            marker = "required" if field_name in required else "optional"
            fields.append(f"{field_name}: {type_name} ({marker})")
        fields_str = ", ".join(fields)
        lines.append(f"- {name}({fields_str}) [mode={entry.get('mode', 'read')}]")
    return "\n".join(lines)


def build_voice_orchestrator_graph():
    """Build the LangGraph workflow for voice orchestration."""
    workflow = StateGraph(VoiceOrchestratorState)
    workflow.add_node("build_plan", build_plan)
    workflow.set_entry_point("build_plan")
    workflow.add_edge("build_plan", END)
    return workflow.compile()


def run_voice_orchestrator(transcript: str) -> Dict[str, Any]:
    """
    Main entry point: transcript -> action plan dict.

    Returns dict with keys: plan, model_name, error (optional).
    """
    initial_state: VoiceOrchestratorState = {
        "transcript": transcript,
        "plan": None,
        "error": None,
        "model_name": "",
        "llm_metrics": [],
    }

    graph = build_voice_orchestrator_graph()
    final = graph.invoke(initial_state)

    return {
        "plan": final["plan"],
        "model_name": final["model_name"],
        "error": final.get("error"),
    }


def generate_summary(results: List[dict]) -> str:
    """Generate a TTS-friendly summary of execution results."""
    llm, model_name = get_llm_with_tracking()
    if not llm:
        successes = sum(1 for r in results if r.get("success"))
        return f"Completed {successes} of {len(results)} actions."

    prompt = VOICE_SUMMARY_PROMPT.format(
        results_json=json.dumps(results, indent=2, default=str)
    )
    response = invoke_llm_with_metrics(llm, prompt, model_name)
    if response.success and response.content:
        return response.content.strip()

    successes = sum(1 for r in results if r.get("success"))
    return f"Completed {successes} of {len(results)} actions."
