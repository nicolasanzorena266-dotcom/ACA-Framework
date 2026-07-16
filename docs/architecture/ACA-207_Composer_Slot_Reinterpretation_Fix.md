# ACA-207 - Composer Slot Reinterpretation Fix

## Alcance

ACA-207 corrige exclusivamente la reinterpretación de
`documentation_available` confirmada por ACA-206. No modifica Runtime,
ConversationState, SemanticAuthority, planificación, misión, Kernel, LLM,
Validator, Studio, Product Layer, plugins, prompts ni benchmarks.

## Causa raíz

`_natural_question_from_required_information()` combinaba dos autoridades para
seleccionar la variante documental:

```python
elif slot == "documentation_available" or "documentacion" in normalize_text(question):
```

En el caso reproducible, el contrato indicaba `slot=user_need`, pero la pregunta
general enumeraba la palabra `documentacion`. El segundo operando anulaba el slot
estructurado y activaba el template de seguros con fotos y presupuesto.

## Código eliminado

Se eliminó únicamente el fallback léxico:

```diff
- elif slot == "documentation_available" or "documentacion" in normalize_text(question):
+ elif slot == "documentation_available":
```

No se cambió ningún template, texto, orden de ramas ni algoritmo de selección de
variantes.

## Autoridad resultante

La variante `documentation_available` se selecciona ahora únicamente cuando el
campo estructurado `slot` posee exactamente ese valor.

Una pregunta con `slot=user_need` puede contener las palabras `documentacion`,
`fotos` o cualquier otro término sin adquirir por ello un nuevo significado.

## Pruebas agregadas

Se agregó `tests/test_narrative_response_composer_slot_authority.py` con dos
regresiones:

1. `slot=user_need` conserva la pregunta original aunque el texto enumere
   `documentacion`; no aparecen `incluyendo fotos` ni `presupuesto`.
2. `slot=documentation_available` continúa seleccionando el template documental
   existente, demostrando que no se cambió el comportamiento autorizado.

Resultado focalizado:

```text
5 passed
```

## Evidencia antes y después

### Turno 1

Usuario:

```text
Hola
```

Antes y después:

```text
Hola. Contame qué necesitás y te oriento.
```

### Turno 2

Usuario:

```text
Quiero dar de baja internet.
```

Antes:

```text
Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido? Asi puedo responder primero la preocupacion mas importante.
```

Después:

```text
Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos? Asi puedo responder primero la preocupacion mas importante.
```

La contaminación introducida por el Composer desaparece: ya no agrega fotos ni
presupuesto y respeta `slot=user_need`.

### Turno 3

Usuario:

```text
¿Qué documentación?
Yo te pedí la baja del servicio.
```

Antes y después:

```text
Para documentacion del siniestro, normalmente conviene tener fotos del dano, presupuesto o comprobante del taller, datos del otro vehiculo y cualquier constancia que te haya pedido el canal. Eso ayuda a que la revision avance con menos idas y vueltas.
```

Este texto no es producido por la regla corregida. ACA-206 demostró que entra al
Composer ya construido por
`kernel/aca_kernel/operations/basic.py:232-240`, particularmente el template de
la línea 234. El Composer lo devuelve mediante `unchanged`.

Eliminar este resultado requeriría modificar la clasificación que produce
`primary_user_need=documentation_guidance`, modificar el Kernel o agregar una
nueva decisión correctiva al Composer. Las tres opciones están expresamente fuera
del alcance de ACA-207.

## Benchmark y suite

### Suite completa

```text
712 passed in 792.23s
```

### Benchmark oficial

```text
Semantic Understanding Score: 98.65%
Benchmark hash: 79c644695143252969f4dde4e4e94b6dbabe6c7813c6733ddaed5340057ac5bd
Report hash: be7207dee98c0f05ac37362e396c84eaf727a3740219af4fac52ec0ce43b3d70
```

### Benchmark adversarial

```text
Semantic Accuracy: 70.72%
Semantic Robustness Score: 73.71%
Benchmark hash: 69bbc81a2cd107a936f63e6b122c110380f31b6916595cba978e50650cb61a47
Report hash: 063803ba90d2f4be1054f80b34117102771340fe5f5a5b03b0c3960f78c8b6b4
```

No hubo regresiones en los benchmarks.

## Deuda técnica observada, no corregida

El mismo helper conserva fallbacks léxicos para `injuries`, `user_role` y
`claim_report_loaded` en `narrative_response_composer.py:246-263`. ACA-207 no los
modifica porque no formaron parte del bug confirmado por ACA-206. Deben evaluarse
en un RC posterior con casos reproducibles propios.

## Estado del criterio de aceptación

| Criterio | Estado | Evidencia |
| --- | --- | --- |
| El Composer deja de reinterpretar `documentation_available` desde texto | Cumplido | La condición depende solo de `slot`. |
| El template documental depende de información estructurada | Cumplido | Las dos regresiones prueban rechazo y aceptación por slot. |
| Desaparece la contaminación introducida por el Composer | Cumplido | El segundo turno ya no agrega fotos ni presupuesto. |
| No cambia ningún componente cognitivo | Cumplido | Un cambio de una línea en el Composer. |
| `basic.py` permanece intacto | Cumplido | No posee diff de ACA-207. |
| Suite completa verde | Cumplido | 712 pruebas aprobadas. |
| La conversación completa deja de mencionar documentación del siniestro | No cumplido dentro del alcance autorizado | El tercer turno proviene del template de Kernel identificado por ACA-206. |

## Conclusión

El bug confirmado en `NarrativeResponseComposer` está corregido de forma mínima:
`slot=user_need` ya no puede convertirse en `documentation_available` por una
palabra presente en la pregunta.

ACA-207 no elimina la contaminación independiente del tercer turno. Afirmar lo
contrario requeriría modificar un componente prohibido o introducir una nueva
decisión semántica en el Composer.
