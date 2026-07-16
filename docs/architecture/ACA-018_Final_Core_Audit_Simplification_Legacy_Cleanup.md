# ACA-018 - Final Core Audit - Simplification & Legacy Cleanup

Status: audit only  
Scope: full repository, no code changes  
Goal: identify what can be simplified or removed without losing ACA capabilities

## 1. Executive Summary

ACA Core is architecturally stable, but the repository is not yet clean enough
to be treated as a minimal Core 1.0 distribution.

The runtime direction is coherent:

- `ConversationState` is the conversation source of truth.
- `ExecutionPlan` and `RuntimeExecutor` own cognitive execution.
- `ToolExecutionContract` governs tool safety.
- Candidate Work, Case State Projection, Governance Gate and Audit Ledger
  validated operational execution without adding a second runtime.
- The first production handoff package tool is integrated through existing
  tool contracts and durable ledger persistence.

The main remaining problem is not missing architecture. It is accumulated
compatibility code.

The largest simplification opportunities are:

1. Remove the remaining `LegacyRuntimeExecutor` dependency after the
   clarification flow is either migrated or absorbed.
2. Remove the public legacy conversational mini-runtime once public adapter
   shadow validation is no longer needed.
3. Split or consolidate the monolithic benchmark implementation in
   `aca_os/evaluation.py`.
4. Archive old public-demo RC and roadmap documents that contradict current
   architecture.
5. Remove local/generated artifacts from version control.

The recommendation is to freeze ACA Core 1.0 as an architecture, but run a
cleanup-only release candidate before tagging the repository.

## 2. Audit Method

The audit inspected:

- repository structure;
- Python module sizes;
- direct references with `rg`;
- runtime and public endpoint code paths;
- operational benchmark code;
- documentation and architecture docs;
- git tracked/local generated artifacts.

No code was changed except this audit document.

## 3. Evidence Snapshot

### Repository Shape

| Area | Files | Python files | Markdown files | Notes |
| --- | ---: | ---: | ---: | --- |
| `aca_os` | 72 | 71 | 1 | Main runtime, public/demo, operational and evaluation code. |
| `tests` | 117 | 117 | 0 | Broad regression suite, includes many public RC and operational benchmarks. |
| `docs` | 118 | 0 | 118 | Heavy historical sprint/ADR/archive load. |
| `benchmarks` | 7 | 0 | 0 | Conversation and operational benchmark datasets. |
| `zero_cost` | 6 | 6 | 0 | Intent/action/flow/execution plan primitives. |
| `kernel` | 13 | 12 | 1 | Kernel and operation registry. |
| `plugins`, `domains`, `examples` | 52 | 12 | 13 | Plugin/domain pack examples and Galicia domain. |

Python footprint:

| Area | Files | LOC | Audit Reading |
| --- | ---: | ---: | --- |
| Core runtime group | 28 | 11,326 | Definitive Core, with one legacy execution dependency. |
| Operational group | 4 | 3,497 | Validated and useful, but still partly projection-heavy. |
| Public legacy group | 6 | 3,645 | Main conceptual duplication outside Core. |
| Evaluation group | 1 | 4,303 | Largest accidental-complexity hotspot. |
| Deploy/demo group | 15 | 3,483 | Useful for hosted demo, not Core. |
| API/CLI/SDK group | 13 | 2,933 | Mostly stable surface adapters. |
| Plugin/domain group | 16 | 1,344 | Core extensibility and examples. |
| Tests | 117 | 10,608 | Important but partly tied to old RC behavior. |
| Other | 32 | 7,066 | Studio, metrics, registries, stores, support code. |
| Total | 232 | 48,205 | Includes tests and post-RC operational additions. |

Largest files:

| File | LOC | Audit Reading |
| --- | ---: | --- |
| `aca_os/conversation_state.py` | 6,698 | Core capability concentration, not dead code. Size is a maintainability debt. |
| `aca_os/evaluation.py` | 4,303 | Multiple benchmark systems in one module. Strong simplification candidate. |
| `aca_os/operational_work_mapper.py` | 1,745 | Validated shadow/projection component. Keep, but avoid expanding it into planner. |
| `aca_os/public_conversation_product_layer.py` | 1,680 | Public adapter plus legacy shadow brain. Strong cleanup candidate. |
| `aca_os/runtime_api_endpoints.py` | 1,114 | Endpoint facade, useful but broad. |

## 4. Definitive Core Map

These components should be considered Core or Core-adjacent and conserved.

| Component | Why It Belongs To Core | Notes |
| --- | --- | --- |
| `ConversationState` | Owns conversation state, facts, slots, topics, plans and fulfillment. | Large, but conceptually central. |
| `ConversationManager` | Owns lifecycle: load, project, commit. | Stable owner boundary. |
| `IntentMatcher`, `ActionPlanner`, `FlowRouter`, `ExecutionPlan` | Deterministic decision chain. | Small and auditable. |
| `PolicyManager` | Governs cognitive authorization/interruption. | Not redundant with governance gate. |
| `RuntimeExecutor` and step handlers | Official execution engine for migrated flows. | Stable enough for Core 1.0. |
| `ToolEngine` and tool contracts | Tool safety/idempotency boundary. | Production integration depends on it. |
| `OperationalWorkMapper` | Passive work projection. | Useful observability; not a planner. |
| `OperationalGovernanceGate` | Operational executability audit. | Not a policy replacement. |
| `OperationalAuditLedger` | Durable operation trace and production receipt boundary. | Needed for real work. |
| `NarrativeResponseComposer` | Verbalizes cognitive state. | Should not select work. |
| Plugin/domain pack validators/loaders | Extensibility boundary. | Keep as platform Core, not conversation Core. |
| Metrics, trace, introspection, Studio read models | Observability. | Keep as read-only projections. |

## 5. Main Findings

### F1 - `LegacyRuntimeExecutor` Still Owns One Official Flow

What it does:

- Contains pre-`RuntimeExecutor` kernel/finalization execution.
- Runs as official engine for `clarification`.
- Runs as validation projection for migrated flows.

Who uses it:

- `ACAOSRuntime.__init__` creates `self.legacy_runtime`.
- `ACAOSRuntime.process` uses it for non-migrated flows.
- `tests/test_runtime_executor_shadow.py` explicitly asserts that
  `clarification` still uses `legacy_runtime`.

Evidence:

- `_runtime_executor_official_flows()` lists:
  `fallback`, `guided_process`, `human_handoff`, `knowledge_lookup`,
  `safe_escalation`, `static_response`.
- `clarification` is absent.
- Tests assert `engine["official_engine"] == "legacy_runtime"` for
  clarification.

What happens if it disappears now:

- Clarification flow breaks.
- Shadow comparison tests break.
- Runtime loses validation projection for migrated flows.

Risk of removal:

- Medium if clarification is migrated or absorbed first.
- High if removed without deciding clarification.

Benefit:

- Removes the last true dual execution architecture.
- Simplifies `ACAOSRuntime.process`.
- Eliminates kernel/finalization compatibility code.

Classification:

- Requires validation.

Recommended cleanup:

1. Decide if `clarification` remains a flow or becomes a conversation-plan
   outcome.
2. Migrate/absorb it.
3. Remove legacy validation comparison after one benchmark cycle.
4. Delete `LegacyRuntimeExecutor`.

### F2 - Public Product Layer Keeps A Legacy Conversational Brain

What it does:

- `PublicConversationProductLayer.run()` sends visible response through
  `ACAOSRuntime`.
- It still runs `_run_legacy_shadow()`.
- Legacy shadow uses `PluginRuntime`, `ConversationProductMemory`,
  `DeterministicDialogueController` and `_project_response()`.

Who uses it:

- `/public-conversation/product-layer/run`.
- Public adapter benchmark.
- Public RC tests asserting `legacy_response` exists and differs from runtime
  response.

Evidence:

- `PublicConversationProductLayer.contract()` declares official pipeline:
  `ACAOSRuntime`, with `legacy_pipeline_mode: shadow_validation`.
- `run()` returns both `response` and `legacy_response`.
- `build_public_runtime_shadow()` classifies divergences as expected
  architectural differences.

What happens if it disappears now:

- Public endpoint can still return runtime response if adapter code is retained.
- Tests expecting legacy shadow metadata fail.
- Public action routing may need a replacement source for `public_actions`.

Risk of removal:

- Medium.

Benefit:

- Removes the largest conceptual duplicate of the modern conversation stack.
- Removes old domain/topic memory (`ConversationProductMemory`) as a possible
  false owner.
- Reduces risk of future regressions where someone reads the legacy response.

Classification:

- Probable elimination.

Recommended cleanup:

1. Keep `PublicConversationProductLayer` as adapter.
2. Remove `_run_legacy_shadow`, `_project_response`,
   `DeterministicDialogueController`, `CognitiveTurnInput`,
   `CognitiveTurnOutput`, and legacy memory fields used only for shadow.
3. Keep `public_actions`, diagnostic projection, opacity filters and reset.
4. Update tests to assert no legacy visible path exists.

### F3 - Older Public Workflow Stack Is A Second Demo Runtime

What it does:

- `PublicConversationWorkflow` implements semantic parse, policy, planner,
  generation and supervision.
- `RepresentativeAnswerComposer` uses that workflow and still contains legacy
  fallback branches.
- `PublicConversationState` stores a public-demo specific state.
- `DemoDomainRuntimeFlowRunner` uses the representative composer and public
  state for `/demo/domain-flow`.

Who uses it:

- `aca_os/demo_domain_flow.py`.
- Several public/studio demo tests.
- `runtime_api_endpoints` exposes demo domain flow endpoints.

Evidence:

- Direct import chain:
  `demo_domain_flow -> RepresentativeAnswerComposer -> PublicConversationWorkflow`.
- `PublicConversationState` says in its docstring: "This is not the full CSM
  implementation."

What happens if it disappears now:

- Demo-domain endpoints and public/studio demo tests break.
- Core runtime does not break.

Risk of removal:

- Medium if demo endpoints are still part of public product.
- Low if archived as historical demo.

Benefit:

- Removes a second semantic/policy/planning/generation stack.
- Clarifies that all conversation goes through `ACAOSRuntime`.

Classification:

- Requires validation.

Recommended cleanup:

- Decide whether `/demo/domain-flow` is a supported product surface.
- If yes, route it through `ACAOSRuntime` or label it explicitly as a legacy
  demo.
- If no, archive the endpoint, tests and supporting composer/workflow/state.

### F4 - `aca_os/evaluation.py` Has Become A Benchmark Monolith

What it does:

- Loads and runs cognitive benchmark.
- Runs public runtime adapter benchmark.
- Runs operational work benchmark.
- Runs real-world benchmark.
- Runs governance benchmark.
- Runs audit-ledger benchmark.
- Runs dry-run benchmark.
- Runs production benchmark.
- Renders reports and aggregates all metrics.

Who uses it:

- `tools/aca_cli.py` benchmark commands.
- Operational tests.
- Cognitive evaluation tests.

Evidence:

- 4,303 LOC.
- 113 top-level definitions.
- Seven benchmark runners and seven renderers.
- Production, dry-run and shadow helper functions share private helpers in one
  namespace.

What happens if it disappears now:

- Benchmarks and CLI benchmark commands break.

Risk of removal:

- High.

Benefit of simplification:

- Lower import coupling.
- Clearer ownership of benchmark families.
- Easier future regression analysis.

Classification:

- Conserve behavior; simplify structure.

Recommended cleanup:

- Do not delete metrics.
- Split mechanically into:
  - `evaluation/conversation.py`;
  - `evaluation/public_adapter.py`;
  - `evaluation/operational_work.py`;
  - `evaluation/governance.py`;
  - `evaluation/ledger.py`;
  - `evaluation/tool_integration.py`;
  - shared `evaluation/common.py`.

This is a module organization cleanup, not a new architecture.

### F5 - Operational Benchmarks Are Useful But Overlapping

What they do:

- `aca_operational_benchmark_v1.json`: synthetic work mapping.
- `aca_operational_real_world_benchmark_v1.json`: real-world multi-turn mapping.
- `aca_operational_governance_benchmark_v1.json`: executability governance.
- `aca_operational_audit_ledger_benchmark_v1.json`: ledger completeness.
- `aca_operational_dry_run_benchmark_v1.json`: dry-run tool chain.
- `aca_operational_production_benchmark_v1.json`: first real tool integration.

Who uses them:

- `aca_os/evaluation.py`;
- CLI benchmark commands;
- operational tests.

What happens if they disappear now:

- Regression gates vanish.
- Operational safety evidence weakens.

Risk of removal:

- Medium to high.

Benefit of simplification:

- Reduce repeated scenario shapes and runner boilerplate.
- Prevent metric drift between benchmark families.

Classification:

- Conserve, but consolidate runners.

Recommended cleanup:

- Keep all benchmark datasets for now.
- Later unify dry-run and production into one "tool integration benchmark"
  runner with different execution modes.
- Keep governance and ledger separate because they measure different safety
  boundaries.

### F6 - `HandoffPackageDryRunAdapter` Is A Backward-Compatible Alias

What it does:

- Subclasses `HandoffPackageAdapter` with no behavior changes.
- Exists only to preserve dry-run benchmark naming.

Who uses it:

- `aca_os/evaluation.py` dry-run registration.
- `tests/test_operational_dry_run_tool.py`.

What happens if it disappears now:

- Dry-run tests and imports fail until updated to use `HandoffPackageAdapter`
  in dry-run mode.

Risk of removal:

- Low.

Benefit:

- Removes a compatibility-only class.
- Makes one adapter responsible for official, dry-run and replay modes.

Classification:

- Elimination probable.

Recommended cleanup:

- Replace references with `HandoffPackageAdapter`.
- Keep benchmark naming in data/report, not in a class alias.

### F7 - `.aca/smoke_memory.json` Is Tracked Runtime Data

What it does:

- Stores smoke-run memory under `.aca`.

Who uses it:

- `tools/smoke_rc1.py` writes to `.aca/smoke_memory.json`.
- It is not needed as committed source.

Evidence:

- `git ls-files` includes `.aca/smoke_memory.json`.
- `.gitignore` includes `.aca/`.

What happens if it disappears from git:

- Smoke script recreates it when run.
- No source behavior changes.

Risk of removal:

- Very low.

Benefit:

- Removes generated state from repository.

Classification:

- Safe elimination.

Recommended cleanup:

- `git rm --cached .aca/smoke_memory.json` in a cleanup sprint.

### F8 - README, ROADMAP and RC1 Docs Are Outdated

What they do:

- Describe RC1-era architecture and next phases.
- README pipeline omits RuntimeExecutor, ConversationState operational
  ownership, Candidate Work, Governance, Ledger and production tool integration.

Who uses them:

- Humans entering the repository.

Evidence:

- `README.md` still says `RC1 Core is closed` and points to old next phases.
- `docs/NEXT_PHASES.md` still recommends packaging, Galicia v2, Studio and RC2
  Runtime as future work, even though many are implemented.
- `docs/ARCHITECTURE.md` starts with an older pipeline and later documents
  newer RuntimeExecutor adoption, creating internal drift.

What happens if they disappear:

- Historical context is lost.

Risk of removal:

- Low for archiving.
- Medium for deletion.

Benefit:

- New contributors stop reading obsolete roadmaps as active direction.

Classification:

- Safe archive/update, not direct deletion.

Recommended cleanup:

- Create a current `CORE_1_0_STATUS.md` or update README/ARCHITECTURE.
- Move sprint docs and RC docs to `docs/archive/` or mark them historical.

### F9 - Public Demo RC Modules Are Historical Product Artifacts

What they do:

- Validate hosted demo polish, release candidate, UX QA, deployment, Render
  config and smoke tests.

Who uses them:

- Runtime endpoint API exposes several public-demo/deploy endpoints.
- Tests cover these endpoints and generated manifests.

What happens if they disappear:

- Public demo deployment endpoints break.
- Core runtime does not break.

Risk of removal:

- Medium if Render/Studio public demo remains supported.
- Low if project freezes Core separately from demo product.

Benefit:

- Separates Core from one hosted demo product lifecycle.

Classification:

- Requires validation.

Recommended cleanup:

- Move public demo RC/deploy code under a clearly non-Core package or archive
  only after confirming Render/Studio dependencies.

### F10 - Endpoint Routing Has Two Large Facades

What it does:

- `RuntimeEndpointAPI` owns endpoint behavior.
- `RuntimeRESTAPI.route()` repeats many route checks before delegating.
- `_local_requester()` in `RuntimeEndpointAPI` also repeats route dispatch for
  local/demo calls.

Who uses it:

- `tools/aca_rest.py`;
- `tools/aca_web.py`;
- Studio API;
- tests.

What happens if simplified incorrectly:

- REST/Studio endpoints regress.

Risk of removal:

- Medium.

Benefit:

- Less route duplication.
- Easier to maintain public/runtime/studio endpoints.

Classification:

- Requires validation.

Recommended cleanup:

- Do not redesign endpoints.
- Generate route dispatch from `RuntimeEndpointAPI.endpoints` or centralize path
  matching in one place.

### F11 - `pyproject.toml` Version Is Stale

What it does:

- Declares package metadata.

Evidence:

- Version is `0.4.0-sprint72b-rc5`, while repository contains Sprints 73-84.

What happens if updated:

- No runtime behavior changes.

Risk:

- Low.

Benefit:

- Aligns package identity with Core 1.0 freeze.

Classification:

- Safe cleanup.

### F12 - `ConversationState` Is Huge But Not Conceptually Redundant

What it does:

- Owns conversational act recognition, slots, facts, mission advancement,
  fact revision, topic stack, response planning, information gain, replanning
  and fulfillment.

Who uses it:

- `ConversationManager`, `ACAOSRuntime`, tests, public projections and
  benchmarks.

What happens if split or reduced carelessly:

- High regression risk.

Risk:

- High for deletion.
- Medium for mechanical module split.

Benefit of simplification:

- Better maintainability and reviewability.

Classification:

- Conserve.

Recommended cleanup:

- Do not remove capabilities.
- If touched later, split mechanically by responsibility behind the same public
  contract, preserving all imports initially.

### F13 - Candidate Work, Case State Projection, Governance and Ledger Are Not Redundant

What they do:

- Candidate Work identifies useful operational work.
- Case State Projection explains operational state from existing runtime data.
- Governance assesses whether selected work would be executable.
- Ledger records how an operation is or would be audited.

Who uses them:

- Operational benchmarks.
- Production handoff package integration.

Why they should not be collapsed now:

- Each answers a different question:
  - What work is present?
  - What is the case state?
  - Is execution allowed?
  - What must be recorded?

What happens if collapsed:

- Operational safety boundaries blur.
- Production integration loses explainability.

Risk:

- High.

Benefit:

- No clear simplification benefit now.

Classification:

- Conserve.

### F14 - Policy and Governance Are Adjacent But Not Duplicated

What they do:

- Policy governs cognitive flow authorization/interruption.
- Governance assesses operational execution readiness.

Who uses them:

- Runtime uses Policy.
- Operational integration uses Governance projection.

What happens if merged:

- Policy becomes responsible for external execution risk, evidence, approval,
  reversibility and tool availability.
- Cognitive/runtime boundary becomes muddy again.

Risk:

- High.

Benefit:

- Superficial file-count reduction only.

Classification:

- Conserve as separate boundaries.

### F15 - Operational Ledger and Runtime Outcomes Are Not Duplicated

What they do:

- Runtime outcomes record cognitive step execution.
- Operational ledger records tool/request/receipt/idempotency/compensation.

Who uses them:

- Runtime introspection;
- operational production benchmark;
- production handoff package tool.

What happens if merged:

- Cognitive trace becomes polluted with external operation persistence concerns.

Risk:

- High.

Benefit:

- Low.

Classification:

- Conserve.

## 6. Simplification Priority List

| Priority | Simplification | Classification | Risk | Benefit |
| --- | --- | --- | --- | --- |
| P0 | Remove tracked `.aca/smoke_memory.json` from git. | Safe elimination | Very low | Removes generated state. |
| P0 | Update README/ROADMAP/ARCHITECTURE to Core 1.0 status. | Safe docs cleanup | Low | Removes architectural confusion. |
| P1 | Resolve `clarification`, then delete `LegacyRuntimeExecutor`. | Requires validation | Medium | Closes runtime migration completely. |
| P1 | Remove public legacy shadow brain from `PublicConversationProductLayer`. | Probable elimination | Medium | Eliminates second public conversation architecture. |
| P1 | Decide whether `/demo/domain-flow` remains supported; archive if not. | Requires validation | Medium | Removes old public workflow stack. |
| P2 | Split `aca_os/evaluation.py` by benchmark family. | Conserve behavior | Medium | Reduces 4,303 LOC monolith. |
| P2 | Replace `HandoffPackageDryRunAdapter` alias with `HandoffPackageAdapter`. | Probable elimination | Low | Removes compatibility-only class. |
| P2 | Consolidate dry-run and production benchmark runner mechanics. | Requires validation | Medium | Reduces benchmark duplication. |
| P3 | Centralize REST/local endpoint dispatch. | Requires validation | Medium | Reduces route duplication. |
| P3 | Archive public demo RC/deploy modules outside Core. | Requires validation | Medium | Separates Core from demo lifecycle. |

## 7. Technical Debt Map

| Debt Area | Severity | Evidence | Recommended Action |
| --- | --- | --- | --- |
| Public legacy conversational stack | High | `PublicConversationProductLayer`, `PublicConversationWorkflow`, `RepresentativeAnswerComposer`, `PublicConversationState` duplicate semantic/policy/planning/generation concepts. | Remove or archive after public adapter validation. |
| Legacy runtime executor | High | Only `clarification` remains official; all migrated flows use it only for validation. | Migrate/absorb clarification, remove comparator. |
| Evaluation monolith | High | 4,303 LOC, 113 top-level definitions, seven benchmark families. | Split mechanically, preserve APIs. |
| Documentation drift | High | README and old RC docs contradict post-Sprint 84 architecture. | Update active docs, archive old sprint docs. |
| Demo/deploy product code in `aca_os` | Medium | Public demo RC, Render, hosted healthcheck modules live beside runtime Core. | Mark non-Core or move later. |
| Endpoint duplication | Medium | REST route matching and local requester duplicate endpoint dispatch. | Centralize dispatch in existing endpoint API. |
| Version drift | Low | `pyproject.toml` still says sprint72b-rc5. | Update metadata during release cleanup. |
| Generated tracked memory | Low | `.aca/smoke_memory.json` is tracked despite `.gitignore`. | Remove from git. |

## 8. Benchmark Audit

| Benchmark | Keep? | Reason |
| --- | --- | --- |
| Cognitive conversation benchmark | Yes | Measures conversational regressions and contract participation. |
| Public runtime adapter benchmark | Temporarily | Needed until public legacy shadow is removed. |
| Operational work benchmark | Yes | Tests work identification. |
| Real-world operational benchmark | Yes | Tests long/messy conversations and ranking stability. |
| Governance benchmark | Yes | Tests execution safety decisions. |
| Audit ledger benchmark | Yes | Tests durable trace completeness. |
| Dry-run tool benchmark | Yes, maybe merge later | Tests tool chain without side effects. |
| Production tool benchmark | Yes | Tests first real reversible operation and persistence. |

Benchmark cleanup should not delete coverage. It should reduce duplicated runner
code and metric boilerplate.

## 9. Documentation Audit

Active documentation needs a cleanup pass.

Outdated or contradictory:

- `README.md`: shows an old Core pipeline and old RC status.
- `docs/ROADMAP.md`: lists old future work as active direction.
- `docs/NEXT_PHASES.md`: predates Studio, RuntimeExecutor and operational
  integration.
- `docs/RC1_*`: useful history, but no longer current operating status.
- `docs/ARCHITECTURE.md`: contains correct newer sections, but starts with an
  older pipeline and still describes shadow/adoption states that are partly
  superseded by production tool integration.

Recommended documentation shape:

- `README.md`: current Core 1.0 overview.
- `docs/ARCHITECTURE.md`: canonical current architecture.
- `docs/architecture/ACA-006` through `ACA-017`: keep as historical design
  record, not active roadmap.
- `docs/archive/`: old sprint and RC closure notes.

## 10. Risks If Cleanup Is Done Too Aggressively

| Risk | Cause | Mitigation |
| --- | --- | --- |
| Breaking `clarification` | Removing `LegacyRuntimeExecutor` too early. | Resolve flow first. |
| Breaking public demo/Render | Removing public RC/deploy modules before endpoint audit. | Validate `/runtime/run`, `/public-conversation/product-layer/run` and Studio. |
| Losing operational safety evidence | Deleting benchmarks instead of consolidating runners. | Keep datasets and metrics. |
| Reintroducing public pipeline duplication | Keeping legacy ProductLayer internals without clear deprecation. | Mark shadow path as removable and add tests for no visible legacy response. |
| Confusing new contributors | Leaving outdated README/ROADMAP active. | Update active docs before Core 1.0 tag. |

## 11. Final Answers

### 1. Can the Core architecture be declared stable?

Parcialmente.

The architecture is stable. The repository still carries important compatibility
and demo/legacy layers that should be cleaned before a clean Core 1.0 release.

### 2. How many important components could be eliminated?

Five important component families are candidates:

1. `LegacyRuntimeExecutor` after clarification is resolved.
2. ProductLayer legacy shadow brain:
   `DeterministicDialogueController`, `_project_response`,
   `ConversationProductMemory` shadow usage.
3. Old public workflow/demo stack:
   `PublicConversationWorkflow`, `RepresentativeAnswerComposer`,
   `PublicConversationState`, `DemoDomainRuntimeFlowRunner`, if demo endpoints
   are archived or rewired.
4. `HandoffPackageDryRunAdapter` compatibility alias.
5. Historical public demo RC/deploy modules from Core distribution, if public
   demo product is separated.

### 3. Biggest source of technical debt

The biggest conceptual debt is the public/demo legacy conversational stack.

The biggest implementation hotspot is `aca_os/evaluation.py`.

Together they represent the main risk: a stable Core surrounded by old
compatibility paths and a benchmark monolith.

### 4. Approximate percentage of current code that belongs to definitive Core

Approximately 65 percent of production Python code belongs to the definitive
Core or stable Core-adjacent surfaces.

The remaining 35 percent is mostly:

- public/demo legacy compatibility;
- deployment/demo product code;
- benchmark implementation accumulation;
- historical adapters and aliases.

Including tests and docs, the definitive Core percentage is lower because the
repository intentionally preserves a lot of validation and history.

### 5. What remains experimental?

- Public legacy shadow comparison.
- Demo-domain conversational workflow.
- Public demo RC/deploy artifacts.
- First production tool integration storage strategy (`JsonlHandoffPackageStore`
  and JSONL ledger store) as reference implementation, not final persistence.
- Operational benchmark runner organization.

Candidate Work, Case State Projection, Governance Gate and Ledger are no longer
conceptually experimental, but their integration remains young.

### 6. Does any conceptual component no longer make sense?

Yes.

The public legacy conversational brain no longer makes sense as a concept in
Core. The public layer should be an adapter only.

`LegacyRuntimeExecutor` also no longer makes sense as a long-term conceptual
component. It remains only as a temporary compatibility executor/comparator.

### 7. Recommend officially freezing ACA Core 1.0?

Si.

Freeze the architecture, not the current repository clutter.

The evidence supports Core 1.0 because the Runtime, ConversationState,
RuntimeExecutor, tool contracts, operational governance and audit ledger are
coherent and validated. The freeze should be followed by a cleanup-only release
candidate that removes or archives legacy/public/demo compatibility layers
without adding new capabilities.
