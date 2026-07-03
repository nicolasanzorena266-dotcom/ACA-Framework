# ADR-0001 — Remove Planner

## Decision

ACA does not use a Planner as a primary architecture component.

## Reason

The Compiler selects cognitive programs.
The Kernel executes operation graphs.
A Planner as a separate component created ambiguity and duplicated responsibility.
