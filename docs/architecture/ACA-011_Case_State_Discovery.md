# ACA-011 - Case State Discovery

Status: Sprint 78 audit  
Scope: Shadow-mode ranking audit and Case State discovery  
Non-goals: no Runtime changes, no response changes, no Candidate Work changes, no Operational Planner, no Case Engine

## 1. Purpose

Sprint 77 showed that the `Candidate Work Model` is already broad enough to
detect the work present in real conversations:

- primary work is almost always correct;
- secondary work is preserved;
- suspended and recovered work are observable;
- blocked work is explicit;
- mixed needs are represented without changing the visible conversation.

The remaining problem is narrow:

```text
Two or more correct candidate works exist, but the first rank is sometimes wrong.
```

Sprint 78 investigates whether that remaining ranking problem is caused by a
missing operational concept: **Case State**.

This Sprint does not implement Case State. It only measures and documents
whether the concept is real.

## 2. What "Case State" Means

Case State is the operational state of the customer case being worked.

It is not the same as conversation state.

| Concept | Owns | Example |
|---|---|---|
| Conversation State | What has happened in the dialogue. | User asked about documents. |
| Conversation Plan | What conversational step should happen next. | Ask the next useful question. |
| Conversation Fulfillment | Whether the turn's conversational goal was satisfied. | The user's question was answered. |
| Candidate Work | What service work is visible in this turn. | Prepare documentation review. |
| Case State | What is true about the operational case. | Claim loaded, documentation pending, waiting analyst. |

Operationally, Case State answers:

```text
What is the current state of the customer's service case,
independent of how the user phrased the latest message?
```

It should be able to represent:

- current stage;
- completed operational milestones;
- pending operational requirements;
- current owner;
- blocked actions;
- external wait states;
- customer-required actions;
- system-required actions;
- evidence supporting each state;
- transitions that changed the case.

## 3. States That Appear Naturally

The benchmark and roleplay corpus naturally expose these operational states.
The names are descriptive, not proposed API names.

| Domain | Natural state | Evidence in conversations |
|---|---|---|
| Claims | Claim not started | "Me chocaron y no se como seguir." |
| Claims | Claim guidance in progress | Active `auto_claim_guidance` mission. |
| Claims | Claim report loaded | "La denuncia ya esta cargada." / "ya quedo cargada." |
| Claims | Claim follow-up needed | "Sigue en tramite", "nadie me contacto." |
| Claims | Waiting for analyst/system | "Hace una semana sigue en tramite." |
| Claims | Documentation unknown | "No se si mande las fotos." |
| Claims | Documentation pending | "No se si faltan documentos." |
| Claims | Documentation available | "Tengo fotos y presupuesto." |
| Claims | Documentation blocked by capability | Upload action is blocked in public plugin manifest. |
| Claims | Repair authorization unknown | "No se si puedo arreglar el auto." |
| Claims | Repair risk active | User may repair before authorization. |
| Billing | Billing issue open | "La factura vino mal." |
| Billing | Billing work suspended | "Dejemos la factura." |
| Connectivity | Connectivity issue open | "No tengo internet." |
| Connectivity | Area outage suspected | "Mis vecinos tampoco." |
| Connectivity | Technical visit needed | "Ya reinicie todo y sigue igual." |
| Connectivity | Technical visit scheduled | "Viene el tecnico manana." |
| Cross-domain | Handoff needed | "Quiero hablar con una persona." |
| Cross-domain | No further action | "Gracias, ya quedo claro." |

These states are about the case, not the wording of the conversation.

## 4. Evidence Already Implicit In ACA

ACA already contains pieces of Case State, but they are distributed.

### ConversationState

`ConversationState` holds:

- `active_mission`;
- `slots`;
- `confirmed_facts`;
- `pending_questions`;
- `topic_stack`;
- `product_state`;
- `derived_state`.

In the observed ranking failure (`RW-051`), `ConversationState` correctly knows
there is an active `auto_claim_guidance` mission, but it does not expose a
durable operational fact like:

```text
claim_report_loaded = true
documentation_state = unknown_or_pending
```

Instead, `confirmed_facts` only preserves `last_raw_payload`.

### ConversationPlan

`ConversationPlan` already contains fact-like steps:

| Plan step | Operational meaning |
|---|---|
| `confirm_claim_report_loaded` | Determine whether the claim exists. |
| `confirm_documentation_available` | Determine whether evidence/docs are complete. |

In `RW-051`, both remain pending even though the user says:

```text
"Listo, la denuncia ya quedo cargada, pero no se si faltan documentos."
```

That means the concept exists, but its ownership is conversational and its
state is not updated as operational case evidence.

### ConversationResponsePlan

`ConversationResponsePlan` identifies:

- primary need: `claim_report_status`;
- secondary need: `documentation_guidance`.

This is useful, but it remains a response-prioritization view. It does not
decide that "claim loaded" is a completed operational milestone and "documents
unknown" is the next case-state concern.

### ConversationFulfillment

`ConversationFulfillment` marks the primary conversational need fulfilled. It
does not mean the operational claim case is complete.

This distinction is important:

```text
The user can be answered while the case still has pending work.
```

### Candidate Work

`CandidateWork` exposes useful state-like signals:

- `status`;
- `work_role`;
- `blocked`;
- `blocked_by`;
- `suspension_reason`;
- `selection_reason`;
- `evidence`.

However, these are projections from the turn. They are not a durable case
state. In `RW-051`, the mapper can mark some candidates as `completed` or
`blocked`, but it has no explicit case-state authority to demote a completed
claim-follow-up in favor of a pending documentation review.

### ExecutionPlan

`ExecutionPlan` shows how ACA executed the cognitive turn:

- flow;
- kernel program;
- steps;
- policy result;
- outcomes.

It does not know whether the external claim is loaded, waiting for analyst, or
missing documentation.

## 5. What Does Not Exist

The following concepts do not exist as first-class operational state:

| Missing concept | Why it matters for ranking |
|---|---|
| Case lifecycle | ACA cannot order work by operational stage. |
| Operational milestones | "Claim loaded" cannot demote claim-intake work. |
| Document state | "Missing docs" cannot become the active case concern. |
| External owner/wait state | Waiting analyst/system remains lexical. |
| State transition history | The mapper cannot distinguish newly completed vs already completed. |
| Case-state evidence | Ranking cannot say which work is active because of case facts. |
| Case-state-derived priority | Work order still depends mostly on text markers and selected response need. |

## 6. Ranking Error Under Audit

The current full real-world benchmark result:

| Metric | Value |
|---|---:|
| Conversations | 56 |
| Turns | 92 |
| Candidate Work Recall | 100% |
| Candidate Work Precision | 92.02% |
| Work Ranking Accuracy | 98.91% |
| Ranking Ambiguity Rate | 1.09% |
| Missing State Evidence | 1 |
| Case State Dependency Rate | 1.09% |
| Ranking Explanation Coverage | 100% |

The only remaining ranking mismatch is `RW-051`.

### RW-051

User:

```text
Listo, la denuncia ya quedo cargada, pero no se si faltan documentos.
```

Expected primary work:

```text
prepare_documentation_review
```

Observed ranked candidates:

| Rank | Operation | Status | Why it appeared |
|---:|---|---|---|
| 1 | `prepare_claim_follow_up` | completed | Strong `denuncia` / claim-status signal. |
| 2 | `prepare_documentation_review` | blocked | `documentos` signal and upload capability blocked. |
| 3 | `close_case_no_action` | completed | `Listo` closure marker. |

The error is not recall. The correct work is present.

The error is ranking.

## 7. Why ACA Chose That Order

ACA chose `prepare_claim_follow_up` first because:

1. `ConversationResponsePlan.primary_user_need` became `claim_report_status`.
2. The user text contains a strong claim marker: `denuncia`.
3. `CandidateWork` preserves the mapper's dominant work as rank 1 for
   compatibility.
4. Documentation appeared as a secondary signal.

This is rational under the current available state.

The missing element is:

```text
The claim report is already loaded, so claim-status/intake work should be
demoted unless there is evidence of waiting, delay, or analyst follow-up.
The active operational concern is now documentation uncertainty.
```

## 8. What Information Was Missing

The ranking needed explicit case-state facts such as:

| Needed fact | Current availability |
|---|---|
| `claim_report_loaded = true` | Present only as raw text, not case state. |
| `claim_report_stage = loaded` | Not present. |
| `documentation_state = unknown_or_pending` | Present only as text marker. |
| `claim_follow_up_needed = false unless delay/contact signal exists` | Not present. |
| `documentation_review_needed = true` | Only inferred as candidate work. |

The Runtime has the raw material. The mapper does not receive an explicit
case-state projection.

## 9. Simulation Without Code Changes

Current ranking:

```text
1. prepare_claim_follow_up
2. prepare_documentation_review
3. close_case_no_action
```

If explicit Case State were available:

```text
case.claim_report = loaded
case.documentation = unknown_or_pending
case.follow_up_delay = false
case.customer_closure = partial
```

Expected ranking:

```text
1. prepare_documentation_review
2. prepare_claim_follow_up
3. close_case_no_action
```

Reason:

- the claim report is no longer the unresolved operational object;
- documentation is the active uncertainty;
- closure is partial because the user immediately adds a remaining concern.

This is the smallest concrete evidence that Case State would improve ranking.

## 10. Does Case State Explain All Remaining Errors?

Current benchmark answer: **Si, for the current measured errors.**

There is only one remaining ranking error. It is fully explained by missing
explicit operational state:

- the right candidates were found;
- the explanation was complete;
- the rank was wrong because the system had no durable state saying that one
  candidate represented completed work and another represented unresolved work.

Broader architectural answer: **Parcialmente.**

Future ranking errors may come from:

- domain-specific priority policy;
- compliance constraints;
- external tool availability;
- customer urgency;
- business SLA;
- unsupported capabilities.

Those are not all Case State. But the current observed error is.

## 11. Should Case State Become Its Own Component?

Not yet.

The concept is real, but the implementation should not start as a new
component. ACA already contains enough distributed evidence to create a derived
case-state projection in Shadow Mode.

Recommended position:

```text
Do not create a Case Engine.
Do not make a new operational owner yet.
Make implicit case-state evidence visible to the mapper first.
```

Why:

- `ConversationState` is already the operational owner of turn state.
- `ConversationPlan` already names case-like facts.
- `ConversationFulfillment` already separates answered vs pending work.
- `CandidateWork` already exposes operational candidates and statuses.

A new component today would likely duplicate existing structures.

When would Case State deserve a component?

Only when ACA starts consuming external operational systems where case state has
an independent lifecycle:

- claim status APIs;
- billing case systems;
- technician dispatch systems;
- document upload/review systems;
- handoff package ownership.

At that point, Case State would no longer be derived from conversation; it
would be synchronized with external systems.

## 12. Risks Of Introducing Case State Too Early

| Risk | Why it matters |
|---|---|
| Duplicate `ConversationState` | Conversation facts and case facts may diverge. |
| Duplicate `ConversationPlan` | Operational steps may look like another plan. |
| Duplicate `ConversationFulfillment` | "Answered" may be confused with "case completed." |
| Premature Case Engine | Adds execution authority before ranking evidence is mature. |
| Domain coupling | Galicia claim states could leak into generic ACA core. |
| Hidden planner | A case-state component might start selecting work indirectly. |

The safest path is to expose Case State as a derived operational projection
first, still in Shadow Mode.

## 13. Benchmark Additions

Sprint 78 adds ranking-specific metrics to the real-world benchmark:

| Metric | Meaning |
|---|---|
| Ranking Ambiguity Rate | Expected primary work exists in candidates but is not rank 1. |
| Missing State Evidence | Ambiguous ranking depends on case state but no case-state evidence is available. |
| Case State Dependency Rate | Ranking decisions that require operational case state. |
| Ranking Explanation Coverage | Candidate set includes enough evidence and selection reasons to explain ranking. |

These metrics do not change Runtime behavior. They only audit the shadow
benchmark.

## 14. Conclusion

The Candidate Work Model is practically complete for detection.

The remaining issue is not:

```text
What work exists?
```

It is:

```text
Which correct work should be first given the operational state of the case?
```

Case State is a real concept, but it already exists partially and implicitly
inside ACA. The next Sprint should not introduce a Case Engine or an
Operational Planner. It should make this implicit state visible as a derived
shadow projection and use the benchmark to determine whether that projection
actually fixes ranking.

Recommended next Sprint:

```text
Case State Projection Shadow Mode
```

Scope:

- derive case-state evidence from existing `ConversationState`, facts,
  `ConversationPlan`, `ConversationFulfillment`, and Candidate Work;
- do not create an operational owner;
- do not modify Runtime behavior;
- use the projection only to explain and later test candidate ranking.
