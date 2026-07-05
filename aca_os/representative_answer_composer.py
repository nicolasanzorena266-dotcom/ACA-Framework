from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aca_os.public_conversation_policy import AdaptiveReplyPolicy
from aca_os.public_conversation_state import PublicConversationState


@dataclass(frozen=True)
class RepresentativeAnswer:
    text: str
    category: str
    next_step: str | None = None


class RepresentativeAnswerComposer:
    """Compose public, representative-style answers from runtime decisions.

    This class is the public language adapter. The runtime may expose domain,
    intent, flow and entities internally; the Studio chat receives a natural
    representative answer driven by conversation state.
    """

    def __init__(self, policy: AdaptiveReplyPolicy | None = None) -> None:
        self.policy = policy or AdaptiveReplyPolicy()

    def compose(
        self,
        *,
        message: str,
        pack: Mapping[str, Any],
        intent: Mapping[str, Any],
        flow: Mapping[str, Any],
        entities: Mapping[str, Any],
        state: PublicConversationState | None = None,
    ) -> RepresentativeAnswer:
        decision = self.policy.decide(
            message=message,
            pack=pack,
            intent=intent,
            flow=flow,
            entities=entities,
            state=state,
        )
        return RepresentativeAnswer(
            text=decision.text,
            category=decision.category,
            next_step=decision.next_step,
        )
