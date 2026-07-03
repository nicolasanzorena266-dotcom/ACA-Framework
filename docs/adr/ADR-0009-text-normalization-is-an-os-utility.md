# ADR-0009 - Text Normalization Is an ACA OS Utility

## Decision

Text normalization belongs to ACA OS as a shared utility.

## Reason

Policy, compiler, domain matching and tool routing need stable normalized text.

## Consequences

- Components should not implement their own accent maps.
- Matching becomes safer across environments.
- Spanish inputs with accents can be handled without mojibake in source files.