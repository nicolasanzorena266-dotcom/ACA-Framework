from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import perf_counter
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from uuid import uuid4

from aca_core.text import normalize_text
from aca_kernel.core.events import Event


SEMANTIC_CONTRACT = "semantic_representation.v1"
SEMANTIC_VERSION = 1
SEMANTIC_AUTHORITY_VERSION = "sa-2.6"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(_freeze(item) for item in sorted(value, key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class SemanticRepresentation:
    """Immutable, turn-scoped interpretation produced only for Shadow observability."""

    representation_id: str
    version: int
    turn_id: str
    language: str
    metadata: Mapping[str, Any]
    semantic_segments: tuple[Mapping[str, Any], ...]
    entities: tuple[Mapping[str, Any], ...]
    events: tuple[Mapping[str, Any], ...]
    assertions: tuple[Mapping[str, Any], ...]
    conversational_act: Mapping[str, Any]
    intents: tuple[Mapping[str, Any], ...]
    goals: tuple[Mapping[str, Any], ...]
    constraints: tuple[Mapping[str, Any], ...]
    uncertainty: tuple[Mapping[str, Any], ...]
    corrections: tuple[Mapping[str, Any], ...]
    contradictions: tuple[Mapping[str, Any], ...]
    topic_structure: Mapping[str, Any]
    grounding: Mapping[str, Any]
    proposed_state_delta: Mapping[str, Any]
    provenance: Mapping[str, Any]
    contract: str = SEMANTIC_CONTRACT

    def __post_init__(self) -> None:
        for name in (
            "metadata",
            "conversational_act",
            "topic_structure",
            "grounding",
            "proposed_state_delta",
            "provenance",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        for name in (
            "semantic_segments",
            "entities",
            "events",
            "assertions",
            "intents",
            "goals",
            "constraints",
            "uncertainty",
            "corrections",
            "contradictions",
        ):
            object.__setattr__(self, name, tuple(_freeze(item) for item in getattr(self, name)))

    def semantic_projection(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "semantic_segments": _thaw(self.semantic_segments),
            "entities": _thaw(self.entities),
            "events": _thaw(self.events),
            "assertions": _thaw(self.assertions),
            "conversational_act": _thaw(self.conversational_act),
            "intents": _thaw(self.intents),
            "goals": _thaw(self.goals),
            "constraints": _thaw(self.constraints),
            "uncertainty": _thaw(self.uncertainty),
            "corrections": _thaw(self.corrections),
            "contradictions": _thaw(self.contradictions),
            "topic_structure": _thaw(self.topic_structure),
            "grounding": _thaw(self.grounding),
            "proposed_state_delta": _thaw(self.proposed_state_delta),
        }

    @property
    def projection_hash(self) -> str:
        payload = _canonical_json(self.semantic_projection()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "representation_id": self.representation_id,
            "version": self.version,
            "turn_id": self.turn_id,
            "language": self.language,
            "metadata": _thaw(self.metadata),
            "semantic_segments": _thaw(self.semantic_segments),
            "entities": _thaw(self.entities),
            "events": _thaw(self.events),
            "assertions": _thaw(self.assertions),
            "conversational_act": _thaw(self.conversational_act),
            "intents": _thaw(self.intents),
            "goals": _thaw(self.goals),
            "constraints": _thaw(self.constraints),
            "uncertainty": _thaw(self.uncertainty),
            "corrections": _thaw(self.corrections),
            "contradictions": _thaw(self.contradictions),
            "topic_structure": _thaw(self.topic_structure),
            "grounding": _thaw(self.grounding),
            "proposed_state_delta": _thaw(self.proposed_state_delta),
            "provenance": _thaw(self.provenance),
            "semantic_projection_hash": self.projection_hash,
        }


class SemanticAuthority:
    """Builds one passive semantic representation without changing Runtime state."""

    component_name = "semantic_authority"
    authority_mode = "shadow"
    version = SEMANTIC_AUTHORITY_VERSION

    def interpret(
        self,
        event: Event,
        *,
        conversation_state: Any,
        turn_number: int,
    ) -> SemanticRepresentation:
        started_perf = perf_counter()
        started_at = utc_now_iso()
        text = str(event.payload or "")
        normalized = normalize_text(text)

        segments = _semantic_segments(text)
        entities = _entities(text, segments)
        events = _events(segments)
        assertions = _assertions(segments, entities)
        conversational_act = _conversational_act(normalized, segments)
        topic_structure = _topic_structure(segments)
        intents = _intents(normalized, segments, topic_structure)
        goals = _goals(segments, intents)
        constraints = _constraints(segments)
        uncertainty = _uncertainty(segments)
        corrections = _corrections(segments)
        contradictions = _contradictions(assertions, conversation_state)
        grounding = _grounding(
            conversation_state,
            segments,
            entities,
            assertions,
            topic_structure,
        )
        proposed_state_delta = _proposed_state_delta(
            assertions=assertions,
            entities=entities,
            events=events,
            corrections=corrections,
            contradictions=contradictions,
            topic_structure=topic_structure,
        )
        finished_at = utc_now_iso()

        base_metadata = {
            "authority": self.component_name,
            "authority_mode": self.authority_mode,
            "authority_version": self.version,
            "conversation_id": str(getattr(conversation_state, "conversation_id", "default")),
            "turn_number": int(turn_number),
            "source_event_type": event.type,
            "started_at": started_at,
            "finished_at": finished_at,
        }
        provenance = {
            "source_event_id": event.id,
            "source_event_type": event.type,
            "source_payload_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_character_count": len(text),
            "source_segment_count": len(segments),
            "analyzers": [
                "segmenter",
                "entity_extractor",
                "event_extractor",
                "assertion_extractor",
                "conversation_act_recognizer",
                "intent_and_goal_projector",
                "topic_projector",
                "grounding_projector",
                "temporal_normalizer",
                "coreference_resolver",
                "negation_scope_analyzer",
            ],
            "generated_at": finished_at,
            "evidence_policy": "source_spans_and_structured_state_references",
        }

        representation = SemanticRepresentation(
            representation_id=str(uuid4()),
            version=SEMANTIC_VERSION,
            turn_id=event.id,
            language=_detect_language(normalized),
            metadata=base_metadata,
            semantic_segments=tuple(segments),
            entities=tuple(entities),
            events=tuple(events),
            assertions=tuple(assertions),
            conversational_act=conversational_act,
            intents=tuple(intents),
            goals=tuple(goals),
            constraints=tuple(constraints),
            uncertainty=tuple(uncertainty),
            corrections=tuple(corrections),
            contradictions=tuple(contradictions),
            topic_structure=topic_structure,
            grounding=grounding,
            proposed_state_delta=proposed_state_delta,
            provenance=provenance,
        )

        latency_ms = round((perf_counter() - started_perf) * 1000, 3)
        serialized_size = len(_canonical_json(representation.to_dict()).encode("utf-8"))
        performance = {
            "construction_latency_ms": latency_ms,
            "representation_size_bytes": serialized_size,
            "entity_count": len(entities),
            "event_count": len(events),
            "assertion_count": len(assertions),
            "topic_count": len(topic_structure.get("topics") or []),
            "segment_count": len(segments),
        }
        return replace(
            representation,
            metadata={**base_metadata, "performance": performance},
        )


def semantic_shadow_record(representation: SemanticRepresentation | None) -> dict[str, Any]:
    if representation is None:
        return {
            "contract": "semantic_authority_shadow.v1",
            "available": False,
            "authority_mode": "legacy",
            "semantic_authority_mode": "shadow",
        }
    data = representation.to_dict()
    metadata = data.get("metadata") or {}
    performance = metadata.get("performance") or {}
    return {
        "contract": "semantic_authority_shadow.v1",
        "available": True,
        "authority_mode": "legacy",
        "semantic_authority_mode": "shadow",
        "semantic_representation_id": representation.representation_id,
        "semantic_version": representation.version,
        "semantic_latency": performance.get("construction_latency_ms", 0.0),
        "semantic_latency_ms": performance.get("construction_latency_ms", 0.0),
        "semantic_projection_hash": representation.projection_hash,
        "semantic_trace": data,
        "timestamps": {
            "started_at": metadata.get("started_at"),
            "finished_at": metadata.get("finished_at"),
            "recorded_at": utc_now_iso(),
        },
        "metrics": dict(performance),
        "decision_influence": False,
        "state_mutation": False,
    }


_TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "insurance_claim": (
        "denuncia",
        "siniestro",
        "choque",
        "chocaron",
        "accidente",
        "reparar",
        "reparacion",
        "arreglar",
        "cristal",
        "poliza",
        "cobertura",
        "taller",
    ),
    "connectivity": (
        "internet",
        "wifi",
        "modem",
        "router",
        "fibra",
        "telefonia",
        "linea movil",
        "sin servicio",
        "sin senal",
        "no funciona el servicio",
    ),
    "billing": ("factura", "cobro", "importe", "monto", "vencimiento", "vence"),
    "documentation": (
        "documentacion",
        "documentos",
        "fotos",
        "presupuesto",
        "archivo",
        "comprobante",
        "formulario",
        "cedula",
    ),
    "identity": ("me llamo", "mi nombre", "como me llamo"),
    "personal_context": ("mi perro", "mi gato", "mascota"),
    "conversation_control": ("olvidate", "volvamos", "seguimos", "resumi", "mas simple", "contame mas"),
}


def _semantic_segments(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    clause_pattern = re.compile(r"[^.!?;]+[.!?;]?", re.UNICODE)
    connector_pattern = re.compile(
        r"\b(?:pero|ademas|ahora|aunque|por otro lado|despues|luego|finalmente)\b",
        re.IGNORECASE,
    )
    protected_text = re.sub(r"(?<=\d)[.,](?=\d)", "¤", text)
    for sentence in clause_pattern.finditer(protected_text):
        raw = text[sentence.start() : sentence.end()]
        offsets = [0]
        offsets.extend(match.start() for match in connector_pattern.finditer(raw) if match.start() > 0)
        offsets.append(len(raw))
        for index in range(len(offsets) - 1):
            local_start, local_end = offsets[index], offsets[index + 1]
            fragment = raw[local_start:local_end].strip(" ,")
            if not fragment:
                continue
            leading = raw[local_start:local_end].find(fragment)
            start = sentence.start() + local_start + max(leading, 0)
            end = start + len(fragment)
            normalized = normalize_text(fragment)
            topics = _topics_for_text(normalized)
            segments.append(
                {
                    "segment_id": f"segment:{len(segments) + 1}",
                    "text": fragment,
                    "normalized_text": normalized,
                    "span": {"start": start, "end": end},
                    "kind": "question" if "?" in fragment else "statement",
                    "topics": topics,
                    "confidence": 1.0,
                }
            )
    if not segments and text.strip():
        stripped = text.strip()
        start = text.find(stripped)
        segments.append(
            {
                "segment_id": "segment:1",
                "text": stripped,
                "normalized_text": normalize_text(stripped),
                "span": {"start": start, "end": start + len(stripped)},
                "kind": "question" if "?" in stripped else "statement",
                "topics": _topics_for_text(normalize_text(stripped)),
                "confidence": 1.0,
            }
        )
    return segments


def _topics_for_text(normalized: str) -> list[str]:
    topics = [
        topic
        for topic, markers in _TOPIC_MARKERS.items()
        if any(marker in normalized for marker in markers)
    ]
    if re.search(r"\$\s*[0-9]|\b(?:pesos?|dinero)\b", normalized):
        topics.append("billing")
    if re.search(r"\b(?:cargad[ao]|enviad[ao]|adjuntad[ao])\s+con\b", normalized):
        topics.append("documentation")
    if re.search(r"\b(?:mande|envie|adjunte)\b\s+\S+", normalized):
        topics.append("documentation")
    return list(dict.fromkeys(topics))


def _evidence_for_match(
    segment: Mapping[str, Any],
    *,
    rule: str,
    match: re.Match[str] | None = None,
    group: int | str = 0,
) -> dict[str, Any]:
    segment_span = dict(segment.get("span") or {})
    segment_start = int(segment_span.get("start") or 0)
    raw = str(segment.get("text") or "")
    if match is None:
        local_start, local_end = 0, len(raw)
    else:
        local_start, local_end = match.span(group)
    absolute_span = {
        "start": segment_start + local_start,
        "end": segment_start + local_end,
    }
    return {
        "segment_id": str(segment.get("segment_id") or ""),
        "span": absolute_span,
        "text": raw[local_start:local_end],
        "rule": rule,
    }


def _clean_entity_value(value: str) -> str:
    cleaned = value.strip(" \t\r\n,.;:!?\"'")
    return re.sub(r"\s+", " ", cleaned)


def _entities(text: str, segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(
        entity_type: str,
        value: Any,
        segment: Mapping[str, Any],
        confidence: float,
        role: str,
        rule: str,
        match: re.Match[str] | None = None,
        group: int | str = 0,
    ) -> None:
        cleaned_value = _clean_entity_value(str(value))
        key = (entity_type, normalize_text(cleaned_value))
        if not key[1] or key in seen:
            return
        seen.add(key)
        evidence = _evidence_for_match(segment, rule=rule, match=match, group=group)
        entities.append(
            {
                "entity_id": f"entity:{len(entities) + 1}",
                "type": entity_type,
                "value": cleaned_value,
                "role": role,
                "confidence": confidence,
                "span": dict(evidence["span"]),
                "rule": rule,
                "evidence": evidence,
            }
        )

    for segment in segments:
        raw = str(segment["text"])
        normalized = str(segment["normalized_text"])
        syntactic_patterns = (
            (
                "person",
                "user",
                0.98,
                "self_identification",
                r"(?:^|\bhola\s*[,.:]?\s+)(?:me llamo|mi nombre es)\s+(.+?)(?=\s*(?:,|[.;!?]|\by\s+(?:tengo|vivo|trabajo)\b|$))",
            ),
            (
                "person",
                "mentioned_person",
                0.95,
                "kinship_naming",
                r"\bmi\s+[\w-]+\s+se llama\s+(.+?)(?=\s+(?:y\s+esta|y\s+vive)\b|[,.;!?]|$)",
            ),
            (
                "animal",
                "user_pet",
                0.97,
                "pet_naming",
                r"\b(?:perro|gato|mascota)\s+(?:se llama|llamad[oa])\s+(.+?)(?=\s+\by\b|[,.;!?]|$)",
            ),
            (
                "organization",
                "employer",
                0.94,
                "employment_relation",
                r"\btrabajo\s+en\s+(.+?)(?=\s+\by\b|[,.;!?]|$)",
            ),
            (
                "organization",
                "service_provider",
                0.95,
                "customer_provider_relation",
                r"\bsoy\s+cliente\s+de\s+(.+?)(?=\s+\by\b|[,.;!?]|$)",
            ),
            (
                "product",
                "used_product",
                0.94,
                "product_noun_phrase",
                r"\b(?:uso\s+el\s+producto|el\s+producto|producto)\s+(.+?)(?=\s+(?:esta|dejo|quedo|y)\b|[,.;!?]|$)",
            ),
            (
                "product",
                "associated_product",
                0.92,
                "association_target",
                r"\basociad[oa]\s+al\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "service",
                "affected_service",
                0.95,
                "service_of_construction",
                r"\bservicio\s+de\s+(.+?)(?=\s+(?:dejo|esta|quedo|no\s+funciona)\b|[,.;!?]|$)",
            ),
            (
                "service",
                "affected_service",
                0.95,
                "failed_service_complement",
                r"\bno\s+funciona\s+(?:el\s+servicio\s+de\s+|el\s+|la\s+)?(.+?)(?=\s+\by\b|[,.;!?]|$)",
            ),
            (
                "service",
                "used_service",
                0.93,
                "service_usage_relation",
                r"\by\s+uso\s+(?!el\s+producto\b)(.+?)(?=\s+en\s+(?:el|la)\b|[,.;!?]|$)",
            ),
            (
                "service",
                "reviewed_service",
                0.9,
                "service_review_relation",
                r"\bpara\s+revisar\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "object",
                "affected_object",
                0.94,
                "collision_patient",
                r"\b(?:choque|chocaron)\s+(?:el|la|un|una)\s+(.+?)(?=\s+en\s+|[,.;!?]|$)",
            ),
            (
                "object",
                "connected_object",
                0.93,
                "connection_target",
                r"\bconectad[oa]\s+al\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "object",
                "owned_object",
                0.92,
                "owned_associated_object",
                r"\btengo\s+(?:un|una)\s+(.+?)(?=\s+asociad[oa]\s+al\b)",
            ),
            (
                "object",
                "mentioned_object",
                0.9,
                "co_location_object",
                r"\bcon\s+(?:el|la)\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "place",
                "residence",
                0.96,
                "residence_location",
                r"\bvivo\s+en\s+(?:el\s+|la\s+)?(.+?)(?=[,.;!?]|$)",
            ),
            (
                "place",
                "event_location",
                0.94,
                "event_location",
                r"\b(?:ocurrid[oa]|choque\s+(?:el|la|un|una)\s+.+?)\s+en\s+(?:el\s+|la\s+)?(.+?)(?=\s+\by\b|[,.;!?]|$)",
            ),
            (
                "place",
                "mentioned_place",
                0.93,
                "person_location",
                r"\b(?:esta|estaba)\s+en\s+(?:el\s+|la\s+)(.+?)(?=[,.;!?]|$)",
            ),
            (
                "place",
                "service_location",
                0.93,
                "determined_location",
                r"\ben\s+(?:el|la)\s+(.+?)(?=\s+(?:para|donde)\b|[,.;!?]|$)",
            ),
            (
                "place",
                "travel_location",
                0.92,
                "travel_location",
                r"\bconmigo\s+en\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "place",
                "work_location",
                0.92,
                "work_dependency_location",
                r"\btrabajar\s+en\s+(.+?)(?=[,.;!?]|$)",
            ),
            (
                "place",
                "scheduled_visit_location",
                0.94,
                "scheduled_visit_location",
                r"\bvisitara\s+(?:el\s+|la\s+)?(.+?)(?=\s+para\s+revisar\b|[,.;!?]|$)",
            ),
            (
                "place",
                "referenced_place",
                0.92,
                "referential_place_phrase",
                r"\beso\s+de\s+(?:el\s+|la\s+)?(.+?)(?=\s*,?\s*\bdonde\b|[,.;!?]|$)",
            ),
            (
                "person",
                "mentioned_person",
                0.92,
                "relative_clause_person",
                r"\bdonde\s+estaba\s+(.+?)(?=\s+con\s+(?:el|la)\b|[,.;!?]|$)",
            ),
            (
                "person",
                "affected_person",
                0.9,
                "affected_person_relation",
                r"\bpara\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'-]*)(?=[,.;!?]|$)",
            ),
        )
        for entity_type, role, confidence, rule, pattern in syntactic_patterns:
            match = re.search(pattern, raw, re.IGNORECASE | re.UNICODE)
            if match:
                add(
                    entity_type,
                    match.group(1),
                    segment,
                    confidence,
                    role,
                    rule,
                    match,
                    1,
                )
        for money in re.finditer(r"\$\s*[0-9][0-9.,]*", raw):
            add("money", money.group(0), segment, 0.99, "amount", "currency_amount", money)
        temporal_patterns = (
            ("relative_duration", r"\bhace\s+(?:un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|[0-9]+)\s+(?:dias?|semanas?|mes(?:es)?|anos?)\b"),
            ("duration", r"\b(?:un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|[0-9]+)\s+(?:dias?|semanas?|mes(?:es)?|anos?)\b"),
            ("relative_day", r"\b(?:ayer|hoy|manana|pasado\s+manana|este\s+momento)\b"),
            ("since_time", r"\bdesde\s+(?:ayer|hoy|el\s+[0-9]{1,2}\s+de\s+[a-z]+)\b"),
            ("calendar_date", r"\b[0-9]{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b"),
            ("weekday_or_period", r"\b(?:el\s+)?(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|la\s+semana\s+proxima|el\s+mes\s+que\s+viene|esta\s+noche)\b"),
            ("clock_time", r"\ba\s+las\s+(?:[0-9]{1,2}(?::[0-9]{2})?|ocho|nueve|diez|once|doce|trece|catorce|quince|dieciseis|diecisiete|dieciocho|diecinueve|veinte)\b|\bal\s+mediodia\b"),
            ("sequence_marker", r"\b(?:primero|despues|luego|finalmente)\b"),
        )
        temporal_spans: list[tuple[int, int]] = []
        for rule, pattern in temporal_patterns:
            for temporal in re.finditer(pattern, normalized, re.IGNORECASE | re.UNICODE):
                if rule == "duration" and any(
                    start <= temporal.start() and temporal.end() <= end
                    for start, end in temporal_spans
                ):
                    continue
                temporal_spans.append(temporal.span())
                add(
                    "temporal_expression",
                    raw[temporal.start() : temporal.end()],
                    segment,
                    0.94,
                    rule,
                    f"temporal_{rule}",
                    temporal,
                )
        future_visit = re.search(
            r"\b(?:visitara|va\s+a\s+visitar|visitara|vendra)\b",
            normalized,
        )
        if future_visit:
            add(
                "temporal_expression",
                "future_visit",
                segment,
                0.9,
                "future",
                "scheduled_visit_future",
                future_visit,
            )
    return entities


def _events(segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    specs = (
        ("vehicle_collision", ("choque", "chocaron", "accidente", "siniestro")),
        ("claim_submitted", ("cargue una denuncia", "denuncia ya esta cargada", "denuncia desde la app")),
        ("claim_waiting", ("sigue en tramite", "nadie me escribio", "nadie me contacto")),
        ("service_outage", ("no funciona el internet", "sin internet", "sin servicio", "no funciona el servicio")),
        ("billing_dispute", ("factura vino mal", "reclamar una factura", "factura de internet")),
        ("vehicle_repair_needed", ("reparar", "arreglar el auto")),
        ("documentation_ready", ("toda la documentacion", "ya envie la documentacion")),
    )
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for segment in segments:
        normalized = str(segment["normalized_text"])
        for event_type, markers in specs:
            matched_markers = [marker for marker in markers if marker in normalized]
            if event_type in seen or not matched_markers:
                continue
            seen.add(event_type)
            first_marker = matched_markers[0]
            marker_match = re.search(re.escape(first_marker), normalized)
            evidence = _evidence_for_match(
                segment,
                rule=f"event_frame:{event_type}",
                match=marker_match,
            )
            events.append(
                {
                    "event_id": f"event:{len(events) + 1}",
                    "type": event_type,
                    "status": "reported",
                    "confidence": 0.9,
                    "span": dict(evidence["span"]),
                    "rule": f"event_frame:{event_type}",
                    "evidence": {**evidence, "matched_markers": matched_markers},
                }
            )
    return events


def _assertions(
    segments: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        predicate: str,
        value: Any,
        segment: Mapping[str, Any],
        confidence: float,
        *,
        rule: str,
        polarity: str | None = None,
        modality: str = "asserted",
        match: re.Match[str] | None = None,
        evidence_override: Mapping[str, Any] | None = None,
    ) -> None:
        effective_polarity = polarity or ("negative" if value is False else "positive")
        key = (predicate, _canonical_json(value), str(segment.get("segment_id") or ""))
        if key in seen:
            return
        seen.add(key)
        evidence = dict(evidence_override or _evidence_for_match(segment, rule=rule, match=match))
        assertions.append(
            {
                "assertion_id": f"assertion:{len(assertions) + 1}",
                "subject": "user_case",
                "predicate": predicate,
                "value": value,
                "polarity": effective_polarity,
                "modality": modality,
                "confidence": confidence,
                "span": dict(evidence.get("span") or {}),
                "rule": rule,
                "evidence": evidence,
            }
        )

    for segment in segments:
        normalized = str(segment["normalized_text"])
        before = len(assertions)
        uncertain = bool(_uncertainty_markers(normalized))
        modality = "uncertain" if uncertain else "asserted"
        injury = re.search(r"\b(?:herid[oa]s?|lesionad[oa]s?)\b", normalized)
        if injury:
            negated, cue = _negation_for_anchor(normalized, injury.start())
            add(
                "injuries",
                not negated,
                segment,
                0.98 if negated else 0.94,
                rule=f"injury_frame:{cue or 'affirmed'}",
                modality=modality,
                match=injury,
            )

        role = re.search(r"\bsoy\s+(asegurad[oa]|tercer[oa])\b", normalized)
        if role:
            role_value = "insured" if role.group(1).startswith("asegur") else "third_party"
            add(
                "user_role",
                role_value,
                segment,
                0.98,
                rule="self_declared_case_role",
                modality=modality,
                match=role,
            )

        claim_loaded = re.search(
            r"\bdenuncia\b.*?\b(?:cargad[oa]|cargue|presentad[oa]|enviad[oa])\b|"
            r"\b(?:cargue|presente|envie)\s+(?:una\s+|la\s+)?denuncia\b",
            normalized,
        )
        claim_not_loaded = re.search(
            r"\b(?:no|todavia\s+no|aun\s+no)\b.*?\b(?:cargue|hice|presente|envie)\b.*?\bdenuncia\b|"
            r"\bdenuncia\b.*?\b(?:no|todavia\s+no|aun\s+no)\b.*?\b(?:cargad[oa]|hecha|presentada|enviada)\b",
            normalized,
        )
        if claim_not_loaded:
            add(
                "claim_report_loaded",
                False,
                segment,
                0.96,
                rule="claim_submission_negated",
                modality=modality,
                match=claim_not_loaded,
            )
        elif claim_loaded:
            negated, cue = _negation_for_anchor(normalized, claim_loaded.end() - 1)
            add(
                "claim_report_loaded",
                not negated,
                segment,
                0.95,
                rule=f"claim_submission_state:{cue or 'affirmed'}",
                modality=modality,
                match=claim_loaded,
            )

        documentation = re.search(r"\b(?:documentacion|documentos)\b", normalized)
        if documentation:
            unavailable = bool(
                re.search(
                    r"\b(?:no\s+tengo|me\s+falta|sin|incomplet[oa])\b.*\b(?:documentacion|documentos)\b",
                    normalized,
                )
            )
            available = bool(
                re.search(
                    r"\b(?:tengo|envie|mande|adjunte)\b.*\b(?:toda\s+la\s+)?(?:documentacion|documentos)\b|"
                    r"\b(?:documentacion|documentos)\b.*\bcomplet[oa]s?\b",
                    normalized,
                )
            )
            if unavailable or available:
                add(
                    "documentation_available",
                    not unavailable,
                    segment,
                    0.94,
                    rule="documentation_availability_frame",
                    modality=modality,
                    match=documentation,
                )

        service_failure = re.search(
            r"\b(?:no\s+funcion\w*|dejo\s+de\s+funcionar|sin\s+(?:internet|servicio|senal|conexion)|"
            r"servicio\s+caid[oa]|se\s+corto)\b",
            normalized,
        )
        if service_failure:
            add(
                "service_available",
                False,
                segment,
                0.96,
                rule="service_failure_frame",
                modality=modality,
                match=service_failure,
            )

        claim_intent = re.search(r"\b(?:hacer|iniciar|presentar|cargar)\b.*?\bdenuncia\b", normalized)
        if claim_intent:
            negated, cue = _negation_for_anchor(normalized, claim_intent.start())
            if negated:
                add(
                    "claim_submission_intent",
                    False,
                    segment,
                    0.95,
                    rule=f"claim_intent_negation:{cue}",
                    modality=modality,
                    match=claim_intent,
                )

        contact = re.search(r"\b(?:llam\w*|contact\w*|escrib\w*)\b", normalized)
        if contact:
            negated, cue = _negation_for_anchor(normalized, contact.start())
            if negated:
                add(
                    "contact_received",
                    False,
                    segment,
                    0.95,
                    rule=f"contact_negation:{cue}",
                    modality=modality,
                    match=contact,
                )

        resolved = re.search(r"\b(?:resolv\w*|solucion\w*|finaliz\w*)\b", normalized)
        if resolved:
            negated, cue = _negation_for_anchor(normalized, resolved.start())
            if negated or "sigue pendiente" in normalized:
                add(
                    "case_resolved",
                    False,
                    segment,
                    0.95,
                    rule=f"case_resolution_negation:{cue or 'pending'}",
                    modality=modality,
                    match=resolved,
                )

        billing_applicability = re.search(
            r"\$\s*[0-9][0-9.,]*.*?\bno\s+era\b.*?\bfactura\b",
            normalized,
        )
        if billing_applicability:
            add(
                "billing_amount_applies",
                False,
                segment,
                0.95,
                rule="billing_amount_denial",
                modality=modality,
                match=billing_applicability,
            )

        recovery_condition = re.search(
            r"\bsi\s+reinicio\s+(?:el\s+|la\s+|un\s+|una\s+)?(.+?),?\s+entonces\b.*?\bpodria\s+volver\b",
            normalized,
        )
        if recovery_condition:
            product = _clean_entity_value(str(segment["text"])[recovery_condition.start(1) : recovery_condition.end(1)])
            add(
                "service_recovery_condition",
                f"restart_{product}",
                segment,
                0.92,
                rule="conditional_service_recovery",
                modality="conditional",
                match=recovery_condition,
            )

        future_claim = re.search(
            r"\bsi\b.*?\bno\s+avanza\s+en\s+(.+?),?\s+\bvoy\s+a\s+reclamar\b",
            normalized,
        )
        if future_claim:
            duration = _clean_entity_value(str(segment["text"])[future_claim.start(1) : future_claim.end(1)])
            add(
                "future_claim_condition",
                f"no_progress_in_{duration}",
                segment,
                0.92,
                rule="conditional_future_claim",
                modality="conditional",
                match=future_claim,
            )

        if len(assertions) == before and normalized not in {"hola", "buenas", "gracias"}:
            predicate = "user_question" if segment.get("kind") == "question" else "user_statement"
            add(
                predicate,
                segment["text"],
                segment,
                0.7,
                rule="unstructured_clause_fallback",
                modality=modality,
            )

    for entity in entities:
        if entity.get("role") == "user":
            segment = _segment_for_id(segments, str((entity.get("evidence") or {}).get("segment_id")))
            if segment:
                add(
                    "user_name",
                    entity.get("value"),
                    segment,
                    0.98,
                    rule="entity_to_identity_fact",
                    evidence_override=entity.get("evidence") or {},
                )
        elif entity.get("role") == "user_pet":
            segment = _segment_for_id(segments, str((entity.get("evidence") or {}).get("segment_id")))
            if segment:
                add(
                    "pet_name",
                    entity.get("value"),
                    segment,
                    0.97,
                    rule="entity_to_pet_fact",
                    evidence_override=entity.get("evidence") or {},
                )
    return assertions


def _negation_for_anchor(normalized: str, anchor_start: int) -> tuple[bool, str | None]:
    before = normalized[max(0, anchor_start - 80) : anchor_start]
    after = normalized[anchor_start : anchor_start + 80]
    cue_patterns = (
        ("todavia_no", r"\btodavia\s+no\b"),
        ("aun_no", r"\baun\s+no\b"),
        ("never", r"\b(?:nunca|jamas)\b"),
        ("negative_indefinite", r"\b(?:nadie|nada|ningun|ninguna|ninguno)\b"),
        ("without", r"\bsin\b"),
        ("not", r"\bno\b"),
    )
    for cue, pattern in cue_patterns:
        matches = list(re.finditer(pattern, before))
        if matches and len(before) - matches[-1].end() <= 55:
            return True, cue
        if cue == "without" and re.search(pattern, after[:30]):
            return True, cue
    return False, None


def _segment_for_id(segments: Sequence[Mapping[str, Any]], segment_id: str) -> Mapping[str, Any] | None:
    return next((segment for segment in segments if segment.get("segment_id") == segment_id), None)


def _conversational_act(normalized: str, segments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = (
        (
            "correction",
            ("me equivoque", "perdon", "nunca dije", "olvidate", "quise decir", "en realidad", "no era eso"),
            0.95,
        ),
        ("recap_request", ("resumime", "resumi"), 0.95),
        ("simplification_request", ("mas simple", "explicamelo simple"), 0.95),
        ("deepening_request", ("contame mas", "profundiza"), 0.94),
        ("continuation", ("seguimos", "continuemos"), 0.94),
        ("closing", ("gracias", "chau", "eso es todo"), 0.9),
        ("topic_shift", ("otra cosa", "ahora quiero", "ahora mi prioridad", "volvamos"), 0.9),
    )
    for act, markers, confidence in candidates:
        matched = [marker for marker in markers if marker in normalized]
        if matched:
            return {"act": act, "confidence": confidence, "evidence": {"matched_markers": matched}}
    if normalized in {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches"}:
        return {"act": "greeting", "confidence": 0.99, "evidence": {"matched_markers": [normalized]}}
    if any(segment.get("kind") == "question" for segment in segments):
        return {"act": "question", "confidence": 0.88, "evidence": {"segment_ids": [segment["segment_id"] for segment in segments if segment.get("kind") == "question"]}}
    return {"act": "new_information", "confidence": 0.75 if normalized else 0.0, "evidence": {"segment_ids": [segment["segment_id"] for segment in segments]}}


def _topic_structure(segments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    topic_segments: dict[str, list[str]] = {}
    primary_hint: str | None = None
    for segment in segments:
        normalized = str(segment["normalized_text"])
        segment_topics = [
            str(topic)
            for topic in segment.get("topics") or []
            if str(topic) != "conversation_control"
        ]
        for topic in segment_topics:
            topic_segments.setdefault(str(topic), []).append(str(segment["segment_id"]))
        explicit_priority = any(
            marker in normalized
            for marker in (
                "lo principal",
                "mi prioridad",
                "lo urgente",
                "mas me preocupa",
                "principalmente",
                "primero",
            )
        )
        focus_shift = any(marker in normalized for marker in ("ahora quiero", "ahora necesito"))
        if segment_topics and (explicit_priority or focus_shift):
            primary_hint = segment_topics[0]
    topics = [
        {
            "topic_id": f"topic:{key}",
            "type": key,
            "status": "observed",
            "segment_ids": segment_ids,
            "priority": 1 if key == primary_hint else index + 2,
            "confidence": 0.9,
        }
        for index, (key, segment_ids) in enumerate(topic_segments.items())
    ]
    if topics and primary_hint is None:
        primary_hint = str(topics[0]["type"])
    relationships = []
    for index in range(len(topics) - 1):
        shared_segments = sorted(
            set(topics[index].get("segment_ids") or [])
            | set(topics[index + 1].get("segment_ids") or [])
        )
        relationships.append(
            {
                "type": "co_occurs",
                "from": topics[index]["topic_id"],
                "to": topics[index + 1]["topic_id"],
                "confidence": 0.88,
                "rule": "topic_co_occurrence",
                "evidence": {"segment_ids": shared_segments, "rule": "topic_co_occurrence"},
            }
        )
    return {
        "topics": topics,
        "primary_topic": f"topic:{primary_hint}" if primary_hint else None,
        "multiple_topics": len(topics) > 1,
        "relationships": relationships,
    }


def _intents(
    normalized: str,
    segments: Sequence[Mapping[str, Any]],
    topic_structure: Mapping[str, Any],
) -> list[dict[str, Any]]:
    intent_for_topic = {
        "insurance_claim": "manage_insurance_claim",
        "connectivity": "restore_connectivity",
        "billing": "review_billing",
        "documentation": "manage_documentation",
        "identity": "recall_identity",
        "personal_context": "recall_personal_fact",
        "conversation_control": "control_conversation",
    }
    intents: list[dict[str, Any]] = []
    for topic in topic_structure.get("topics") or []:
        topic_type = str(topic.get("type"))
        intents.append(
            {
                "intent_id": f"intent:{len(intents) + 1}",
                "type": intent_for_topic.get(topic_type, "open_request"),
                "topic_id": topic.get("topic_id"),
                "priority": topic.get("priority"),
                "confidence": topic.get("confidence", 0.8),
                "explicit": True,
                "evidence": {"segment_ids": list(topic.get("segment_ids") or [])},
            }
        )
    if normalized in {"hola", "buenas", "buen dia", "buenas tardes", "buenas noches"}:
        intents.append({"intent_id": "intent:1", "type": "greet", "priority": 1, "confidence": 0.99, "explicit": True, "evidence": {"matched_markers": [normalized]}})
    if any(marker in normalized for marker in ("asesor", "persona real", "humano", "representante")):
        intents.append({"intent_id": f"intent:{len(intents) + 1}", "type": "request_human", "priority": 1, "confidence": 0.97, "explicit": True, "evidence": {"matched_markers": [marker for marker in ("asesor", "persona real", "humano", "representante") if marker in normalized]}})
    if not intents and any(segment.get("kind") == "question" for segment in segments):
        intents.append({"intent_id": "intent:1", "type": "request_information", "priority": 1, "confidence": 0.72, "explicit": True, "evidence": {"segment_ids": [segment["segment_id"] for segment in segments]}})
    if not intents and normalized:
        intents.append({"intent_id": "intent:1", "type": "open_request", "priority": 1, "confidence": 0.55, "explicit": False, "evidence": {"segment_ids": [segment["segment_id"] for segment in segments]}})
    return _dedupe_by(intents, "type")


def _goals(segments: Sequence[Mapping[str, Any]], intents: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    goals: list[dict[str, Any]] = []
    for segment in segments:
        normalized = str(segment["normalized_text"])
        priority_match = re.search(
            r"\b(?:lo\s+principal\s+es|mi\s+prioridad\s+es|lo\s+urgente\s+es|"
            r"lo\s+que\s+mas\s+me\s+preocupa\s+es)\s+(.+?)(?=\s*,?\s*\baunque\b|[,.;!?]|$)",
            normalized,
        )
        if priority_match:
            target = _clean_entity_value(
                str(segment["text"])[priority_match.start(1) : priority_match.end(1)]
            )
            evidence = _evidence_for_match(
                segment,
                rule="explicit_goal_priority",
                match=priority_match,
                group=1,
            )
            goals.append(
                {
                    "goal_id": f"goal:{len(goals) + 1}",
                    "type": "achieve_user_outcome",
                    "target": target,
                    "priority": 1,
                    "confidence": 0.96,
                    "span": dict(evidence["span"]),
                    "rule": "explicit_goal_priority",
                    "evidence": evidence,
                }
            )
            continue
        if segment.get("kind") == "question":
            evidence = _evidence_for_match(segment, rule="interrogative_goal")
            goals.append(
                {
                    "goal_id": f"goal:{len(goals) + 1}",
                    "type": "obtain_answer",
                    "target": segment["text"],
                    "priority": 1,
                    "confidence": 0.9,
                    "span": dict(evidence["span"]),
                    "rule": "interrogative_goal",
                    "evidence": evidence,
                }
            )
        elif any(marker in normalized for marker in ("quiero", "necesito", "tengo que")):
            evidence = _evidence_for_match(segment, rule="volitional_goal")
            goals.append(
                {
                    "goal_id": f"goal:{len(goals) + 1}",
                    "type": "achieve_user_outcome",
                    "target": segment["text"],
                    "priority": 1,
                    "confidence": 0.84,
                    "span": dict(evidence["span"]),
                    "rule": "volitional_goal",
                    "evidence": evidence,
                }
            )
    if not goals:
        for intent in intents:
            evidence = dict(intent.get("evidence") or {})
            evidence.setdefault("rule", "intent_to_goal_projection")
            goals.append(
                {
                    "goal_id": f"goal:{len(goals) + 1}",
                    "type": "satisfy_intent",
                    "target": intent.get("type"),
                    "priority": intent.get("priority", 1),
                    "confidence": intent.get("confidence", 0.6),
                    "rule": "intent_to_goal_projection",
                    "evidence": evidence,
                }
            )
    return goals


def _constraints(segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    specs = (
        ("urgency", ("vence manana", "urgente", "hoy", "cuanto antes")),
        ("work_dependency", ("para trabajar", "necesito el auto", "necesito internet")),
        ("access_limit", ("no tengo acceso", "no puedo", "no funciona")),
    )
    for segment in segments:
        normalized = str(segment["normalized_text"])
        for kind, markers in specs:
            matched = [marker for marker in markers if marker in normalized]
            if matched:
                constraints.append({"constraint_id": f"constraint:{len(constraints) + 1}", "type": kind, "value": segment["text"], "confidence": 0.88, "evidence": {"segment_id": segment["segment_id"], "matched_markers": matched}})
    return constraints


def _uncertainty(segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for segment in segments:
        normalized = str(segment["normalized_text"])
        matched = _uncertainty_markers(normalized)
        if matched:
            marker_match = re.search(re.escape(matched[0]), normalized)
            evidence = _evidence_for_match(
                segment,
                rule="epistemic_uncertainty_marker",
                match=marker_match,
            )
            values.append(
                {
                    "uncertainty_id": f"uncertainty:{len(values) + 1}",
                    "type": "user_uncertainty",
                    "scope": segment["text"],
                    "confidence": 0.9,
                    "span": dict(evidence["span"]),
                    "rule": "epistemic_uncertainty_marker",
                    "evidence": {**evidence, "matched_markers": matched},
                }
            )
    return values


def _uncertainty_markers(normalized: str) -> list[str]:
    patterns = (
        r"\bno\s+se\b",
        r"\bno\s+estoy\s+segur[oa]\b",
        r"\bno\s+recuerdo\b",
        r"\bno\s+puedo\s+precisar\b",
        r"\b(?:creo|quizas|tal\s+vez|puede\s+ser|capaz)\b",
    )
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(match.group(0) for match in re.finditer(pattern, normalized))
    return matches


def _corrections(segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for segment in segments:
        normalized = str(segment["normalized_text"])
        operation: str | None = None
        target: str | None = None
        rule: str | None = None
        marker_match: re.Match[str] | None = None
        retraction_match = re.search(
            r"\b(?:olvidate(?:\s+de)?|no\s+importa|dejal[oa](?:\s+por\s+ahora)?|"
            r"dejemos\s+(?:ese|esa|el|la)?\s*tema|mejor\s+hablemos\s+de\s+otra\s+cosa)\b",
            normalized,
        )
        denial_match = re.search(r"\bnunca\s+dije\b", normalized)
        replacement_match = re.search(
            r"\b(?:me\s+equivoque|perdon|quise\s+decir|en\s+realidad|no\s+era\s+eso)\b",
            normalized,
        )
        if retraction_match:
            operation = "retract"
            rule = "discourse_retraction"
            marker_match = retraction_match
            target_match = re.search(
                r"\b(?:olvidate(?:\s+de)?|no\s+importa(?:\s+lo\s+de)?|dejemos(?:\s+ese)?\s+tema(?:\s+de)?)\s+(.+)",
                normalized,
            )
            target = target_match.group(1).strip(" .!?;") if target_match else None
        elif denial_match:
            operation = "deny_prior_assertion"
            rule = "explicit_prior_denial"
            marker_match = denial_match
            target = normalized.split("nunca dije", 1)[1].strip() or None
        elif replacement_match:
            operation = "replace_prior_assertion"
            rule = "explicit_correction_marker"
            marker_match = replacement_match
        if operation:
            evidence = _evidence_for_match(
                segment,
                rule=str(rule),
                match=marker_match,
            )
            corrections.append(
                {
                    "correction_id": f"correction:{len(corrections) + 1}",
                    "operation": operation,
                    "target": target,
                    "status": "proposed",
                    "confidence": 0.9 if target else 0.78,
                    "span": dict(evidence["span"]),
                    "rule": rule,
                    "evidence": evidence,
                }
            )
    return corrections


def _contradictions(assertions: Sequence[Mapping[str, Any]], conversation_state: Any) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    confirmed = dict(getattr(conversation_state, "confirmed_facts", {}) or {})
    current_values: dict[str, Any] = {}
    for assertion in assertions:
        predicate = str(assertion.get("predicate") or "")
        if predicate in {"user_statement", "user_question"}:
            continue
        value = assertion.get("value")
        prior_current = current_values.get(predicate, value)
        if predicate in current_values and prior_current != value:
            contradictions.append({"contradiction_id": f"contradiction:{len(contradictions) + 1}", "type": "within_turn", "fact": predicate, "previous_value": prior_current, "new_value": value, "confidence": min(float(assertion.get("confidence") or 0.0), 0.95), "evidence": dict(assertion.get("evidence") or {})})
        current_values[predicate] = value
        if predicate not in confirmed:
            continue
        previous = confirmed[predicate]
        if isinstance(previous, Mapping) and previous.get("contract") == "conversational_fact.v1":
            previous = previous.get("value")
        if previous != value:
            contradictions.append({"contradiction_id": f"contradiction:{len(contradictions) + 1}", "type": "against_conversation_state", "fact": predicate, "previous_value": previous, "new_value": value, "confidence": float(assertion.get("confidence") or 0.0), "evidence": dict(assertion.get("evidence") or {})})
    return contradictions


def _grounding(
    conversation_state: Any,
    segments: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]],
    assertions: Sequence[Mapping[str, Any]],
    topic_structure: Mapping[str, Any],
) -> dict[str, Any]:
    confirmed = dict(getattr(conversation_state, "confirmed_facts", {}) or {})
    asserted_predicates = {str(item.get("predicate")) for item in assertions}
    matched_facts = sorted(predicate for predicate in asserted_predicates if predicate in confirmed)
    topic_stack = list(getattr(conversation_state, "topic_stack", []) or [])
    active_topics = [str(item.get("id") or item.get("topic_id")) for item in topic_stack if item.get("status") in {"active", "resumed"}]
    pending_questions = list(getattr(conversation_state, "pending_questions", []) or [])
    relevant_context = dict(getattr(conversation_state, "relevant_context", {}) or {})
    resolved_coreferences, unresolved_coreferences = _resolve_coreferences(
        segments=segments,
        current_entities=entities,
        relevant_context=relevant_context,
        topic_stack=topic_stack,
        topic_structure=topic_structure,
    )
    return {
        "conversation_id": str(getattr(conversation_state, "conversation_id", "default")),
        "prior_turn_count": int(getattr(conversation_state, "turn_count", 0) or 0),
        "active_mission": dict(getattr(conversation_state, "active_mission", None) or {}),
        "active_topic_references": active_topics,
        "observed_topic_references": [topic.get("topic_id") for topic in topic_structure.get("topics") or []],
        "matched_confirmed_fact_keys": matched_facts,
        "available_confirmed_fact_keys": sorted(str(key) for key in confirmed),
        "pending_question_references": [question.get("id") or question.get("slot") for question in pending_questions],
        "relevant_memory_references": sorted(str(key) for key in relevant_context),
        "resolved_coreferences": resolved_coreferences,
        "unresolved_coreferences": unresolved_coreferences,
        "grounding_mode": "read_only_shadow",
    }


def _resolve_coreferences(
    *,
    segments: Sequence[Mapping[str, Any]],
    current_entities: Sequence[Mapping[str, Any]],
    relevant_context: Mapping[str, Any],
    topic_stack: Sequence[Mapping[str, Any]],
    topic_structure: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contextual_entities = [
        {
            "type": value.get("type"),
            "value": value.get("value"),
            "source": "conversation_context",
        }
        for value in relevant_context.values()
        if isinstance(value, Mapping) and value.get("type") and value.get("value") is not None
    ]
    candidates = [
        {"type": item.get("type"), "value": item.get("value"), "source": "current_turn"}
        for item in current_entities
        if item.get("type") and item.get("value") is not None
    ] + contextual_entities

    active_topics = [
        str(item.get("type") or item.get("id") or item.get("topic_id") or "").removeprefix("topic:")
        for item in topic_stack
        if item.get("status") in {"active", "resumed"}
    ]
    observed_primary = str(topic_structure.get("primary_topic") or "").removeprefix("topic:")
    topic_candidates = [topic for topic in active_topics + [observed_primary] if topic]

    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen_mentions: set[tuple[str, str, str]] = set()

    def select_entity(entity_type: str, normalized_segment: str) -> Mapping[str, Any] | None:
        typed = [item for item in candidates if item.get("type") == entity_type]
        mentioned = [
            item
            for item in typed
            if normalize_text(item.get("value") or "") in normalized_segment
        ]
        return (mentioned or typed)[-1] if (mentioned or typed) else None

    mention_specs = (
        (r"\bmi\s+(?:perro|gato|mascota)\b", "animal", "possessive_pet_reference"),
        (r"\bese\s+producto\b", "product", "typed_demonstrative_reference"),
        (r"\bella\b", "person", "personal_pronoun_reference"),
        (r"\b(?:ese|este|aquel)\b", "object", "masculine_demonstrative_reference"),
        (r"\b(?:esa|esta|aquella)\b", "object", "feminine_demonstrative_reference"),
        (r"\baquello\b", "product", "neutral_product_reference"),
        (r"\beso\b", "place", "neutral_context_reference"),
    )
    for segment in segments:
        normalized = str(segment.get("normalized_text") or "")
        for pattern, target_type, rule in mention_specs:
            for mention in re.finditer(pattern, normalized):
                mention_text = mention.group(0)
                candidate = select_entity(target_type, normalized)
                if candidate is None and target_type == "object":
                    candidate = select_entity("product", normalized)
                evidence = _evidence_for_match(segment, rule=rule, match=mention)
                if candidate is None:
                    unresolved.append(
                        {
                            "mention": mention_text,
                            "target_type": target_type,
                            "confidence": 0.0,
                            "rule": rule,
                            "evidence": evidence,
                        }
                    )
                    continue
                key = (
                    normalize_text(mention_text),
                    str(candidate.get("type")),
                    normalize_text(candidate.get("value") or ""),
                )
                if key in seen_mentions:
                    continue
                seen_mentions.add(key)
                resolved.append(
                    {
                        "mention": mention_text,
                        "target_type": candidate.get("type"),
                        "target_value": candidate.get("value"),
                        "confidence": 0.94 if candidate.get("source") == "current_turn" else 0.88,
                        "rule": rule,
                        "evidence": evidence,
                    }
                )

        main_topic = re.search(r"\btema\s+principal\b", normalized)
        if main_topic:
            evidence = _evidence_for_match(
                segment,
                rule="discourse_focus_reference",
                match=main_topic,
            )
            if topic_candidates:
                resolved.append(
                    {
                        "mention": main_topic.group(0),
                        "target_type": "topic",
                        "target_value": topic_candidates[0],
                        "confidence": 0.82,
                        "rule": "discourse_focus_reference",
                        "evidence": evidence,
                    }
                )
            else:
                unresolved.append(
                    {
                        "mention": main_topic.group(0),
                        "target_type": "topic",
                        "confidence": 0.0,
                        "rule": "discourse_focus_reference",
                        "evidence": evidence,
                    }
                )
    return resolved, unresolved


def _proposed_state_delta(
    *,
    assertions: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    corrections: Sequence[Mapping[str, Any]],
    contradictions: Sequence[Mapping[str, Any]],
    topic_structure: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_assertions = [
        dict(assertion)
        for assertion in assertions
        if assertion.get("predicate") not in {"user_statement", "user_question"}
    ]
    return {
        "contract": "semantic_state_delta_proposal.v1",
        "applied": False,
        "decision_influence": False,
        "owner": "semantic_authority_shadow",
        "assertions_to_review": candidate_assertions,
        "entity_upserts": [dict(entity) for entity in entities],
        "event_additions": [dict(event) for event in events],
        "correction_requests": [dict(item) for item in corrections],
        "contradictions_to_review": [dict(item) for item in contradictions],
        "topic_candidates": [dict(topic) for topic in topic_structure.get("topics") or []],
        "reason": "SA-1 observes proposed changes but never applies them",
    }


def _detect_language(normalized: str) -> str:
    if not normalized:
        return "und"
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    spanish = len(tokens & {"hola", "que", "como", "tengo", "quiero", "necesito", "no", "mi", "me", "una", "el", "la", "para"})
    english = len(tokens & {"hello", "what", "how", "have", "want", "need", "not", "my", "the", "for"})
    if english > spanish:
        return "en"
    return "es" if spanish else "und"


def _dedupe_by(values: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        marker = str(value.get(key) or "")
        if marker in seen:
            continue
        seen.add(marker)
        output.append(dict(value))
    return output
