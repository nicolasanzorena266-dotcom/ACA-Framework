# Sprint 72B — Public Conversation Product Layer + Plugin Execution Bridge

Sprint 72B connects the public conversation layer to real plugin execution.

## Principle

```text
hooks propose
runtime applies
trace records
```

## Delivered contract

- Added `PluginExecutionContext` with conversation, request, plugin, capability, mode, state, route and manifest context.
- Added manifest-level `public_actions` with capability, enabled state, real-tool requirement and disabled reason.
- Enforced that every public action points to a namespaced handled or blocked capability.
- Executed plugin semantic, policy and planner hooks during the public flow.
- Added segmented developer trace fields: trace id, conversation id, request id, plugin id, capability, event type, timestamp and safe payload.
- Added a public conversation product layer that returns public trace, diagnostic view and developer trace separately.
- Added client-mode exposure filtering for technical implementation language.
- Added capability-claim filtering for false operational claims.
- Added multi-turn cristales tests in client support mode.
- Cleaned README mojibake arrows.

## Acceptance rule

If a hook exists and is not executed during the corresponding public flow, Sprint 72B fails.

## Public action rule

Every `public_action` must point to an existing handled capability or a declared blocked capability.

## Boundary

The public chat must not consume the developer trace directly.

The plugin no longer only declares what it can do. It now participates in how ACA understands, decides, responds and presents itself.

## RC2 — Public Demo Product Repair

Sprint 72B-RC2 is an acceptance repair for the public demo. It does not add new product features before closing the broken public experience.

### RC2 acceptance fixes

- Replaced the public shell with a chat-left / actions-right layout.
- Removed the visible public sidebar and phone-frame sizing that could cut off the input.
- Kept the chat input visible on desktop `1366x768` and mobile `390x844` viewports.
- Moved process and diagnostic actions into the right panel/modal instead of the chat.
- Preserved client-support wording in the visible chat.
- Kept observability actions from appending messages to the conversation.
- Added persistent public conversation memory across hosted REST calls.
- Repaired the multi-turn cristales flow so repeated context is not re-asked after the user already supplied it.

### RC2 hard rules

```text
If Render loads but the chat speaks like the framework, it fails.
If the input is cut off, it fails.
If an observability action writes to visible chat, it fails.
If an enabled button does not execute a real action, it fails.
If the user already said cristales and ACA asks for the case type again, it fails.
```

## RC3 — Routing and Response Repair

Sprint 72B-RC3 is an acceptance repair for public conversational quality. It keeps the RC2 visual structure and fixes routing / response behavior exposed during manual Render testing.

### RC3 acceptance fixes

- Explicit billing terms such as factura, pago, vencimiento, importe or monto no longer route to `insurance.claims` when no billing plugin exists.
- Explicit domain terms take precedence over generic operational words such as estado, trámite or seguimiento.
- Billing messages fall back to `generic.open_chat` with general orientation and without operational billing claims.
- Repetition/frustration markers such as “ya te dije” trigger a repair response instead of repeating the same template.
- Visible client responses must reflect the semantic core of the user message.
- The public example button runs the Galicia/cristales acceptance flow instead of a generic billing/status scenario.

### RC3 hard rules

```text
If the user says factura and ACA routes to insurance.claims, it fails.
If the user says ya te dije and ACA repeats the same template, it fails.
If the response does not mention the semantic core of the user message, it fails.
If generic.open_chat handles billing, it must not pretend to access billing systems.
```

## RC4 — Conversational Memory and Public Surface Cleanup

Sprint 72B-RC4 is an acceptance repair for public conversation continuity. It does not introduce the full cognitive state model, tools, handoffs or new domain plugins. It only fixes the broken public behavior exposed after RC3.

### RC4 acceptance fixes

- Public memory stores minimal billing facts: domain, issue focus, expected amount, received amount and frustration signals.
- Explicit user data beats generic prompts. If the user gives `$110` and `$150000`, ACA must reuse those values.
- Short follow-ups such as “el importe” and “sí” continue the active billing goal instead of resetting the conversation.
- Repetition/frustration markers such as “ya te dije”, “ya te dijee” and “bue...” repair using the accumulated context.
- Cristales follow-ups keep answering the actual question, including whether documentation should be shared through the chat and what to do after 48 business hours.
- Public Studio removes old visible scaffolding from Sprint 64, Demo Polish, UX QA, `max-height: 590px` and runtime-link labels.

### RC4 hard rules

```text
If ACA already knows the topic, asking “contame el tema concreto” fails.
If the user gave concrete amounts, the response must reuse them.
If the user selects “el importe”, ACA must advance on importe.
If the user says “sí” after a billing next step, ACA must continue that step.
If the user shows frustration, ACA must repair with context instead of restarting.
If /studio exposes old Sprint 64 or layout scaffolding text, it fails.
```
