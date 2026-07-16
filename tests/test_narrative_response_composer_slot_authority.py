from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState
from aca_os.narrative_response_composer import NarrativeResponseComposer


def _state_with_required_information(*, response: str, slot: str, question: str) -> CognitiveState:
    return CognitiveState(
        response=response,
        selected_program="fallback",
        active_mission={"type": "general_orientation"},
        facts={
            "conversation_response_plan": {
                "plan": {
                    "primary_user_need": {"key": "understand_user_need"},
                    "required_information": [
                        {
                            "slot": slot,
                            "question": question,
                            "purpose": "responder primero la preocupacion mas importante",
                        }
                    ],
                }
            }
        },
    )


def test_user_need_slot_is_not_reinterpreted_from_question_text():
    question = "Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos?"
    response = f"{question} Asi puedo responder primero la preocupacion mas importante."
    state = _state_with_required_information(
        response=response,
        slot="user_need",
        question=question,
    )

    result = NarrativeResponseComposer().compose(
        state=state,
        event=Event(type="user_message", payload="Quiero dar de baja internet."),
        conversation_state=ConversationState(conversation_id="slot-authority-user-need", turn_count=2),
    )

    assert result.response == response
    assert "incluyendo fotos" not in result.response
    assert "presupuesto" not in result.response


def test_documentation_template_still_requires_structured_documentation_slot():
    question = "Tenes toda la documentacion?"
    response = f"{question} Asi puedo responder primero la preocupacion mas importante."
    state = _state_with_required_information(
        response=response,
        slot="documentation_available",
        question=question,
    )

    result = NarrativeResponseComposer().compose(
        state=state,
        event=Event(type="user_message", payload="Quiero dar de baja internet."),
        conversation_state=ConversationState(conversation_id="slot-authority-documentation", turn_count=2),
    )

    assert result.response.startswith("Tenes toda la documentacion, incluyendo fotos, presupuesto")
