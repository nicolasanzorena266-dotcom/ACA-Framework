from aca_kernel.core.state import CognitiveState


def explain_state(state: CognitiveState) -> str:
    lines = [
        f"conversation_id: {state.conversation_id}",
        f"version: {state.version}",
    ]

    if state.selected_program:
        lines.append(f"program: {state.selected_program}")

    if state.active_mission:
        lines.append(f"mission: {state.active_mission.get('type')}")

    if state.policy_result:
        lines.append(
            "policy: "
            f"{state.policy_result.get('decision')} "
            f"({state.policy_result.get('reason')})"
        )

    if state.tool_evidence:
        lines.append(f"tool_evidence: {list(state.tool_evidence.keys())}")

    lines.append("timeline:")
    for step in state.timeline:
        changed = ", ".join(step["changes"].keys())
        lines.append(
            f"- v{step['from_version']} -> v{step['to_version']}: "
            f"{step['operation']} [{changed}]"
        )

    return "\n".join(lines)