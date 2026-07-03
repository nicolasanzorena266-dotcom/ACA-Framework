# ACA Framework Specification — RC1 Core

## 1. Purpose

ACA Framework defines an explicit architecture for cognitive agents.

It separates reasoning from language generation, domain knowledge and model providers.

## 2. Layers

1. ACA Kernel
2. ACA OS
3. Domain Packs
4. Plugins
5. Studio

## 3. Kernel

The Kernel:

- executes operations;
- maintains immutable Cognitive State Models;
- records the timeline;
- validates operation contracts;
- does not know domains;
- does not call LLMs directly.

## 4. ACA OS

ACA OS coordinates behavior around the Kernel.

Official components:

- Conversation Manager
- Mission Manager
- Policy Manager
- Memory Engine
- Tool Engine
- Context Manager

## 5. Domain Packs

Domain Packs provide domain-specific knowledge, policies, scenarios and tool descriptions.

Domain Packs never modify Kernel behavior.

## 6. Invariants

1. ACA processes events, not raw conversations.
2. All reasoning occurs through the CSM.
3. Every operation has a contract.
4. Every state change is traceable.
5. Tools produce evidence, not final responses.
6. The Kernel is model-agnostic.
7. Domains are plugins.
