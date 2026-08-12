# Component I: Policy Engine

Status: TESTED | Decision contract: 1.0

The policy engine evaluates validated structured action attributes and returns an
immutable `ALLOW`, `DENY`, or `REQUIRE_APPROVAL` decision bound to the action's
canonical SHA-256 digest. Explicit denial and security-weakening rules take
precedence. Sensitive/destructive effects, production, publishing, external
communication, spending, and restricted data require approval.

Task prose and metadata cannot change classification. The engine does not grant or
persist approvals, resolve secrets, authorize filesystem/network access, or execute
effects. Those remain separate durable enforcement gates.
