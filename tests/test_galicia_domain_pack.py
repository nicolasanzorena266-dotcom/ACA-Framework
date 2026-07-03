from domains.galicia.domain_pack import load_galicia_domain


def test_loads_galicia_domain_pack():
    domain = load_galicia_domain()

    assert domain.name == "galicia"
    assert "cleas" in domain.concepts
    assert "franquicia" in domain.concepts
    assert "informational_limits" in domain.policies
    assert "auto_claim_guidance" in domain.scenarios


def test_domain_context_is_structured():
    domain = load_galicia_domain()
    context = domain.context()

    assert context["domain"] == "galicia"
    assert context["concepts"]["cleas"]["name"] == "CLEAS"
    assert "No consultar CRM por defecto." in context["policies"]["informational_limits"]["rules"]