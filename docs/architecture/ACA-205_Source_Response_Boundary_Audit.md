# ACA-205 - Source Response Boundary Audit

## Turno 1

Usuario:

```text
Hola
```

==============================

SOURCE_RESPONSE

```text
Hola. Contame qué necesitás y te oriento.
```

==============================

LLM_RAW_RESPONSE

```text
Hola. Contame qué necesitás y te oriento.
```

==============================

VISIBLE_RESPONSE

```text
Hola. Contame qué necesitás y te oriento.
```

==============================

SOURCE_RESPONSE == LLM_RAW_RESPONSE: **iguales**

LLM_RAW_RESPONSE == VISIBLE_RESPONSE: **iguales**

## Turno 2

Usuario:

```text
Quiero dar de baja internet.
```

==============================

SOURCE_RESPONSE

```text
Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido? Asi puedo responder primero la preocupacion mas importante.
```

==============================

LLM_RAW_RESPONSE

```text
¿Tenes toda la documentación, incluyendo fotos, presupuesto o lo que te pidieron? Asi puedo responder primero la preocupación más importante.
```

==============================

VISIBLE_RESPONSE

```text
¿Tenes toda la documentación, incluyendo fotos, presupuesto o lo que te pidieron? Asi puedo responder primero la preocupación más importante.
```

==============================

SOURCE_RESPONSE == LLM_RAW_RESPONSE: **diferentes**

LLM_RAW_RESPONSE == VISIBLE_RESPONSE: **iguales**

```text
SOURCE
- Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido? Asi puedo responder primero la preocupacion mas importante.

LLM
+ ¿Tenes toda la documentación, incluyendo fotos, presupuesto o lo que te pidieron? Asi puedo responder primero la preocupación más importante.
```

## Turno 3

Usuario:

```text
¿Qué documentación?
Yo te pedí la baja del servicio.
```

==============================

SOURCE_RESPONSE

```text
Para documentacion del siniestro, normalmente conviene tener fotos del dano, presupuesto o comprobante del taller, datos del otro vehiculo y cualquier constancia que te haya pedido el canal. Eso ayuda a que la revision avance con menos idas y vueltas.
```

==============================

LLM_RAW_RESPONSE

```text
Para la documentación del siniestro, suele ser útil tener fotos del daño, el presupuesto o comprobante del taller, datos del otro vehículo y cualquier constancia que te haya pedido el canal. Esto ayuda a que la revisión avance con menos idas y vueltas.
```

==============================

VISIBLE_RESPONSE

```text
Para la documentación del siniestro, suele ser útil tener fotos del daño, el presupuesto o comprobante del taller, datos del otro vehículo y cualquier constancia que te haya pedido el canal. Esto ayuda a que la revisión avance con menos idas y vueltas.
```

==============================

SOURCE_RESPONSE == LLM_RAW_RESPONSE: **diferentes**

LLM_RAW_RESPONSE == VISIBLE_RESPONSE: **iguales**

```text
SOURCE
- Para documentacion del siniestro, normalmente conviene tener fotos del dano, presupuesto o comprobante del taller, datos del otro vehiculo y cualquier constancia que te haya pedido el canal. Eso ayuda a que la revision avance con menos idas y vueltas.

LLM
+ Para la documentación del siniestro, suele ser útil tener fotos del daño, el presupuesto o comprobante del taller, datos del otro vehículo y cualquier constancia que te haya pedido el canal. Esto ayuda a que la revisión avance con menos idas y vueltas.
```

## Respuestas objetivas

¿El `source_response` ya hablaba de siniestros, documentación, taller, fotos y vehículo antes de invocar al LLM?

**Sí.**

¿El LLM agregó información nueva?

**No.**

¿El LLM modificó solamente el estilo o modificó también el contenido?

**Modificó solamente el estilo.**

¿La respuesta visible es exactamente la respuesta del LLM?

**Sí, en los tres turnos.**

## Conclusión

**El error nace antes del LLM.** El segundo `source_response` ya pregunta por documentación y fotos después de que el usuario solicita la baja de internet. El tercer `source_response` ya introduce siniestro, fotos, taller y otro vehículo. El modelo no inventa ese contenido: solamente reformula el texto recibido, y Studio muestra exactamente esa reformulación.
