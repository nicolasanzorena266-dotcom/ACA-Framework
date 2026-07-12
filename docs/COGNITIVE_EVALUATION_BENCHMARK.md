# Cognitive Evaluation Benchmark

ACA now includes a permanent benchmark for evaluating conversation behavior with the real Runtime.

This benchmark is not a technical accuracy gate. It measures whether the cognitive architecture changes the conversation in observable ways.

## Purpose

The benchmark answers four questions:

- What cognitive contracts actually participate in realistic conversations?
- Which decisions changed the user-facing response?
- Where did ACA feel natural or robotic?
- Which layers add complexity without observed benefit?

## Conversation Bank

The default fixture lives at:

`benchmarks/conversations/aca_cognitive_benchmark_v1.json`

It covers denuncias, coverage, franquicia, CLEAS, documentation, timing, anxious users, topic shifts, corrections, partial answers, long conversations, interruptions, recaps, simplification, deepening and handoff.

## Running

Run the full benchmark:

```powershell
python tools/aca_cli.py benchmark --format markdown
```

Write JSON output:

```powershell
python tools/aca_cli.py benchmark --format json --output benchmark-result.json
```

Run a single scenario:

```powershell
python tools/aca_cli.py benchmark --scenario prioridad_fotos_vs_reparacion --format markdown
```

Run a bounded smoke sample:

```powershell
python tools/aca_cli.py benchmark --max-scenarios 3 --format dict
```

## Metrics

The benchmark records:

- objective fulfillment
- turn count
- questions asked
- questions avoided
- topic changes
- focus recovery
- mission changes
- replanning
- fulfillment
- recovery actions
- repeated questions
- memory, fact, topic stack, slot, conversation plan and response plan usage

## Cognitive Audit

For every scenario ACA reports:

- contracts used
- contracts never used
- decisions that changed the response
- contracts observed but not tied to response changes
- removable or questionable steps for that scenario
- deterministic conversational error classifications

## Rule

Future cognitive Sprints should run this benchmark before and after changes.

A Sprint improves ACA only when it improves conversation quality without hiding regressions in the cognitive audit.
