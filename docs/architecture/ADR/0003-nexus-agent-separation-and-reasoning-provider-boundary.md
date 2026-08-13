# ADR-0003: Separate NEXUS Agent from NEXUS OS and reasoning providers

Status: Accepted

Date: 2026-08-13

## Context

NEXUS OS already provides provider-neutral orchestration, policy, approval,
checkpoint, evidence, and qualification primitives. A conversational product must
not give a language model authority to execute tools, mutate acceptance criteria,
approve its own actions, or assert completion without evidence. Users also require
both local operation without a commercial API key and optional hosted providers.

## Decision

The product is divided into three independently versioned boundaries:

1. **NEXUS Agent** owns conversational objective intake, clarification, candidate
   specification generation, progress explanation, and presentation of results.
2. **NEXUS OS** remains the sole authority for validation, policy, approvals,
   controlled execution, recovery, evidence, and qualification.
3. **Reasoning providers** are replaceable, untrusted components reached only
   through provider adapters. An API key is one credential mechanism, not an
   architectural requirement; local endpoints may require no external credential.

Every model proposal follows the path `proposal -> schema validation -> policy ->
approval when required -> controlled execution -> evidence -> qualification`.
There is no model-to-tool bypass. Conversation state is distinct from durable run
state. The first product increment freezes agent contracts only; it does not claim
an implemented agent, local model integration, application service, or user interface.

## Consequences

- Local, organization-hosted, and commercial models can share one trust boundary.
- Model quality and model authorization remain separate; capabilities are promoted
  only from qualification evidence.
- The agent may draft acceptance criteria, but only an authorized actor can approve
  a specification, and later changes invalidate that approval binding.
- Additional schemas, lifecycle checks, API operations, conformance tests, and UI
  work are required before a user-facing agent exists.

## Alternatives rejected

- Embedding one foundation model in the core would create vendor and license coupling.
- Letting the model directly run tools would bypass deterministic policy and evidence.
- Treating chat history as runtime state would weaken atomic recovery and auditability.

## Migration impact

Existing NEXUS OS contracts remain valid. New agent contracts compose with the
control plane and do not change qualified kernel semantics.
