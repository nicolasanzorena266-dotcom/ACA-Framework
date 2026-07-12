from aca_core.text import normalize_text
from aca_kernel.compiler.programs import PROGRAMS
from aca_kernel.core.events import Event
from aca_kernel.core.graph import OperationGraph
from aca_kernel.core.state import CognitiveState


class GraphCompiler:
    def compile(self, event: Event, state: CognitiveState | None = None) -> OperationGraph:
        planned_program = _planned_kernel_program(state)
        if planned_program is not None:
            return PROGRAMS.get(planned_program, PROGRAMS["fallback"])

        text = normalize_text(event.payload)
        if text in {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches"}:
            return PROGRAMS["greeting"]
        if any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro", "tercero"]):
            return PROGRAMS["auto_claim_guidance"]
        return PROGRAMS["fallback"]


def _planned_kernel_program(state: CognitiveState | None) -> str | None:
    if state is None:
        return None
    execution_plan = state.facts.get("zero_cost_execution_plan")
    if not isinstance(execution_plan, dict):
        return None
    program = execution_plan.get("kernel_program")
    if program:
        return str(program)
    flow = execution_plan.get("flow")
    return str(flow) if flow else None
