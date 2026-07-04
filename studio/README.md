# ACA Studio

ACA Studio is the read-only Runtime Intelligence surface for ACA.

It renders runtime contracts only:

- Session summary
- Runtime Health
- Decision Graph
- Metrics
- Components
- Component Registry
- Timeline
- Execution Trace
- Event Bus

Studio must never contain runtime decision logic. Interfaces consume the same Runtime Introspection API that future REST and MCP surfaces will consume.
