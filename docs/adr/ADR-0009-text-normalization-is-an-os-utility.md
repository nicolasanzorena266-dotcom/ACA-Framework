# ADR-0009 - Text Normalization Is a Core Framework Boundary

## Decision

Text normalization belongs to `aca_core.text` as a shared framework utility.
ACA OS, Kernel, plugins, runtime services and public conversation layers must
consume this boundary instead of implementing local normalization helpers.

## Reason

Policy, compiler, domain matching, tool routing and public conversation flows
need stable normalized text. Normalization is not OS-specific and must remain
domain-agnostic, deterministic and reusable by future framework components.

## Consequences

- Components should not implement their own accent maps.
- Components should not keep local wrappers that only delegate to the boundary.
- Matching becomes safer across environments.
- Spanish inputs with accents can be handled without mojibake in source files.
- Mojibake repair, accent stripping, casing and whitespace collapse are owned by
  `aca_core.text`.
