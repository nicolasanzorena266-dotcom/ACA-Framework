# ACA-206 - NarrativeResponseComposer Decision Audit

## Alcance

Se ejecutó exactamente esta conversación:

```text
Hola

Quiero dar de baja internet.

¿Qué documentación? Yo te pedí la baja del servicio.
```

La instrumentación fue temporal y estuvo limitada al módulo
`NarrativeResponseComposer`. Cada wrapper llamó a la implementación original y
devolvió su resultado sin alterarlo. No se modificó ningún archivo funcional ni
ninguna respuesta visible.

## Respuesta principal

La regla defectuosa del Composer está en
`aca_os/narrative_response_composer.py:264`:

```python
elif slot == "documentation_available" or "documentacion" in normalize_text(question):
```

En el segundo turno, las variables reales fueron:

```text
slot = user_need
question = Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos?
```

`slot == "documentation_available"` era falso, pero el segundo operando era
verdadero porque la pregunta general enumeraba la palabra `documentacion`. La
regla reinterpretó entonces un `user_need` como `documentation_available`.

Esa clasificación llamó a `_question_variant()` y seleccionó el template de
`aca_os/narrative_response_composer.py:310`:

```text
Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido?
```

Esta es la línea exacta donde el Composer introduce por primera vez `fotos` y
`presupuesto` en la respuesta del segundo turno.

## Flujo de decisiones

### Turno 1: `Hola`

Texto recibido por el Composer:

```text
Hola. Contame qué necesitás y te oriento.
```

```text
_should_preserve_response
  Resultado: Entró
  Motivo: selected_program = greeting
  Línea: narrative_response_composer.py:481
  Texto producido: Hola. Contame qué necesitás y te oriento.

_clean_surface_template
  Resultado: No cambió el texto

Ganadora: preserved_specialized_response
```

El retorno temprano de `compose()` en las líneas 37-43 descartó todas las ramas
posteriores.

### Turno 2: `Quiero dar de baja internet.`

Texto recibido por el Composer:

```text
Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos? Asi puedo responder primero la preocupacion mas importante.
```

Variables principales:

```text
primary_need = understand_user_need
required_information.slot = user_need
mission_type = general_orientation
selected_program = fallback
turn_count = 2
```

Árbol ejecutado:

```text
Rule A: _should_preserve_response
  Resultado: No entró
  Motivo: flow=fallback, sin tool evidence, selected_program=fallback

Rule B: _compose_repetition_repair
  Resultado: No entró
  Motivo: no hubo marcador léxico de repetición y la misión no era auto_claim_guidance

Rule C: _compose_claim_status
  Resultado: No entró
  Motivo: primary_need=understand_user_need y el mensaje no contenía denuncia ni siniestro

Rule D: _repair_generic_template
  Resultado: No entró
  Motivo: el texto no coincidió con ningún generic template y la misión era general_orientation

Rule E: _reformulate_planned_question_in_response
  Resultado: Entró
  Motivo: la pregunta planificada estaba presente en la respuesta y turn_count=2

  _natural_question_from_required_information
    slot real: user_need
    matching léxico: documentacion
    condición ganadora: narrative_response_composer.py:264
    rama seleccionada: documentation_available

  _question_variant
    turn_count: 2
    índice: (2 - 1) % 5 = 1
    template elegido: narrative_response_composer.py:310

  reemplazo aplicado: narrative_response_composer.py:345-347

Respuesta final:
  Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido? Asi puedo responder primero la preocupacion mas importante.

Ganadora: planned_question_reformulation
Retorno ganador: narrative_response_composer.py:88-89
```

El matching no se hizo contra `Quiero dar de baja internet.`. Se hizo contra la
pregunta generada que enumeraba `arreglo`, `denuncia`, `documentacion` y
`tiempos`.

### Turno 3: `¿Qué documentación? Yo te pedí la baja del servicio.`

Texto recibido por el Composer:

```text
Para documentacion del siniestro, normalmente conviene tener fotos del dano, presupuesto o comprobante del taller, datos del otro vehiculo y cualquier constancia que te haya pedido el canal. Eso ayuda a que la revision avance con menos idas y vueltas.
```

Variables principales:

```text
primary_need = documentation_guidance
required_information = []
mission_type = general_orientation
selected_program = fallback
turn_count = 3
```

Árbol ejecutado:

```text
Rule A: _should_preserve_response
  Resultado: No entró

Rule B: _compose_repetition_repair
  Resultado: No entró
  Motivo: no hubo marcador de repetición y la misión no era auto_claim_guidance

Rule C: _compose_claim_status
  Resultado: No entró
  Motivo: primary_need=documentation_guidance no pertenece a las claves de claim status

Rule D: _repair_generic_template
  Resultado: No entró
  Motivo: el texto no coincidió con los templates genéricos

Rule E: _reformulate_planned_question_in_response
  Resultado: No entró
  Motivo: required_information estaba vacío

Rule F: _clean_surface_template
  Resultado: No cambió el texto

Ganadora: unchanged
Retorno ganador: narrative_response_composer.py:91-95
```

El Composer recibió `siniestro`, `fotos`, `taller` y `vehiculo` en su entrada y
los devolvió sin cambios. No los produjo en este turno.

## Origen exacto de cada término

### 1. `documentación`

La primera aparición anterior al Composer fue producida por
`_reformulated_question_for_slot()` en
`aca_os/conversation_state.py:2362-2363` para `slot == "user_need"`:

```text
Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos?
```

La primera función del Composer que convirtió esa mención incidental en una
pregunta documental fue `_natural_question_from_required_information()` mediante
la condición de la línea 264. `_question_variant()` materializó el texto visible
en la línea 310.

### 2. `siniestro`

Fue producido antes del Composer por
`_response_from_conversational_response_plan()` en
`kernel/aca_kernel/operations/basic.py:172`. La rama seleccionada fue
`primary_key == "documentation_guidance"` en la línea 232 y el término aparece
literalmente en el template de la línea 234.

### 3. `vehículo`

Fue producido por la misma función, rama y template del Kernel:
`kernel/aca_kernel/operations/basic.py:232-240`, con la aparición literal en la
línea 234. `taller` y las `fotos` del tercer turno tienen el mismo origen.

## Tipo de origen

| Contenido | Origen |
| --- | --- |
| Pregunta general que enumera `documentacion` | Mapeo de slot en `ConversationState`, antes del Composer. |
| Conversión de `user_need` en `documentation_available` | Heurística léxica del Composer, línea 264. |
| `fotos` y `presupuesto` del segundo turno | Template del Composer, línea 310. |
| `siniestro`, `taller`, `vehiculo` y guía documental del tercer turno | Template del Kernel gobernado por `ConversationResponsePlan.primary_user_need=documentation_guidance`, líneas 232-240. |

## Clasificación del Composer

**Reinterpretando información.**

La evidencia determinante es que el Composer recibe un dato estructurado
`slot=user_need`, pero vuelve a inferir su tipo mediante matching sobre el texto
de la pregunta. La palabra `documentacion`, presente solo como una alternativa
en una enumeración, domina al slot estructurado y cambia la rama. La inserción de
`fotos` y `presupuesto` es la consecuencia del template asociado a esa
reinterpretación.

## Template incorrecto

Template elegido:

```text
narrative_response_composer.py:310
Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido?
```

Alternativa descartada:

```text
narrative_response_composer.py:309
default = Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos?
```

La alternativa `default` ocupaba el índice 0. Fue descartada porque
`turn_count=2` produjo el índice 1 en las líneas 317-319. Las variantes de las
líneas 311-313 tampoco fueron consideradas porque el índice seleccionado fue
exactamente 1.

## Conclusión objetiva

La primera contaminación atribuible al Composer ocurre en
`aca_os/narrative_response_composer.py:264`: una condición léxica permite que la
palabra `documentacion` anule el `slot=user_need`. La respuesta documental se
materializa en la línea 310.

La contaminación más amplia del tercer turno no nace en el Composer. Nace en el
template de `kernel/aca_kernel/operations/basic.py:234`, seleccionado por
`primary_user_need=documentation_guidance`; el Composer la recibe y la conserva
mediante su rama final `unchanged`.
