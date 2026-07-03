from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.graph import OperationGraph
from aca_kernel.compiler.programs import PROGRAMS

def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    for a, b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n"}.items():
        text = text.replace(a, b)
    return text

class GraphCompiler:
    def compile(self, event: Event, state: CognitiveState | None = None) -> OperationGraph:
        text = normalize_text(str(event.payload))
        if text in {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches"}:
            return PROGRAMS["greeting"]
        if any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro", "tercero"]):
            return PROGRAMS["auto_claim_guidance"]
        return PROGRAMS["fallback"]
