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
