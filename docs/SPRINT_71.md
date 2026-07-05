# Sprint 71 — LLM-assisted Conversational Workflow Runtime

Estado: RC10

## Decisión técnica

Sprint 71 deja de tratar la conversación pública como una suma de reglas de copy. El objetivo es un workflow conversacional asistido por LLM, con comportamientos agentic controlados por ACA.

Contrato central:

- ACA gobierna.
- El LLM propone.
- Las políticas autorizan.
- Las herramientas ejecutan.
- El supervisor controla.
- La traza explica.

La implementación actual no requiere un proveedor LLM externo para correr tests ni para la demo pública. Incluye un fallback offline determinista que respeta los mismos contratos. El LLM queda preparado como capacidad futura del `SemanticUnderstandingLayer` y del `NaturalReplyGenerator`, no como reemplazo del runtime.

## Contratos implementados

- `SemanticParse`: intención gruesa, tema, objetivo del usuario, hechos conocidos, datos faltantes, señales de interacción, confianza, requerimiento de herramienta, riesgo y acción solicitada.
- `InteractionSignals`: frustración, confusión, urgencia y repetición como señales conversacionales, no como diagnóstico emocional.
- `PolicyDecision`: acción solicitada, herramienta requerida, disponibilidad, autorización, fallback y motivo.
- `PlannerDecision`: próxima acción, estrategia, aclaración, herramienta, handoff, contenido obligatorio y contenido prohibido.
- `SupervisorResult`: resultado estructurado de control, issues, reescritura y bloqueo.
- `Public Trace`: qué entendió, qué contexto usó, qué decidió hacer y qué límite encontró.
- `Developer Trace`: trace_id, session_id, semantic_parse, state_before, state_after_projection, planner_decision, policy_decision, guardrail_result, tool_requests, fallback_used, latency y model_used.

## Flujo

Usuario → Input Guardrail → Semantic Understanding Layer → State Update → Policy Layer → Hybrid Conversation Planner → Tool / Knowledge / Handoff Decision → Optional Execution → State Update → Natural Reply Generator → Output Supervisor → Respuesta final → Public Trace + Developer Trace.

## Criterios de aceptación

- No responder desde el mensaje aislado cuando existe contexto activo.
- No pedir datos ya dados.
- No repetir el mismo fallback.
- No fingir herramientas reales.
- No prometer estados, pagos, reparaciones ni plazos exactos no verificables.
- Preparar derivación con contexto cuando el usuario pide persona real.
- Mantener chat-first UI y proceso como detalle secundario.

## Caso conversacional cubierto

Flujo validado por tests multi-turn:

1. “cargué la denuncia desde la app pero no tengo novedades”
2. “tuve un choque. cargué la denuncia en la app. pero sigo esperando”
3. “Si, ya lo hice a eso”
4. “Cuales son los plazos?”
5. “documentacion”
6. “Ya la envie a la documentacion”
7. “ya me dijiste mil veces eso”
8. “quiero hablar con una persona. derivame”

El resultado esperado es continuidad de estado, orientación contextual, bloqueo de tool inexistente y resumen de derivación.
