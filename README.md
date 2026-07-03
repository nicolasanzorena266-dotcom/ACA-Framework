# ACA Framework

ACA Framework is an engineering framework for designing cognitive agents.

ACA is not a chatbot template and it is not a prompt collection. It separates cognition into explicit, auditable layers.

## Core architecture

```text
Event
  ↓
Conversation Manager
  ↓
Mission Manager
  ↓
Policy Manager
  ↓
Compiler
  ↓
Operation Graph
  ↓
ACA Kernel
  ↓
CSM Timeline
  ↓
Response / Tool Request / Escalation
```

## Status

Release Candidate 1 — Core Bootstrap.

This repository is now the single source of truth for ACA Framework.
Older ZIP prototypes are historical artifacts.

## Structure

```text
specification/   Official ACA specification
kernel/          ACA Kernel reference implementation
aca_os/          ACA OS components
runtime/         Runtime orchestration
sdk/             Developer SDK
domains/         Domain Packs, starting with Galicia Seguros
studio/          Debug and visualization tooling
tests/           Compliance and behavior tests
examples/        Runnable examples
docs/            ADRs, RFCs, roadmap and architecture notes
tools/           Development utilities
```
