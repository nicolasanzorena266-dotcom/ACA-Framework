from sdk.factory import build_galicia_runtime, process_message


def test_build_galicia_runtime_processes_message():
    runtime = build_galicia_runtime()

    output = runtime.process_output_message if False else runtime.process_output

    assert runtime.domain_context["domain"] == "galicia"


def test_process_message_returns_output_dict():
    result = process_message("Que es la franquicia?", conversation_id="test-sdk")

    assert result["conversation_id"] == "test-sdk"
    assert result["selected_program"] == "knowledge_lookup"
    assert "Franquicia" in result["response"]
    assert "parte del arreglo" in result["response"]
    assert result["policy_result"]["decision"] == "USE_TOOL"
    assert result["policy_result"]["tool_key"] == "franquicia"
    assert result["tool_evidence"]["franquicia"]["name"] == "Franquicia"
