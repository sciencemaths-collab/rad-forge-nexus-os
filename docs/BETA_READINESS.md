# RAD Agent Beta Readiness

RAD Agent Alpha 4 is a strongly tested pre-release. The word **Beta** is reserved for evidence that
the complete default installed-user journey works without repository knowledge while preserving
the same qualification, approval, sandbox, and evidence boundaries.

## Promotion gates

All of the following must pass before the package classifier and semantic version move to Beta:

1. At least one supported real LLM provider/model/adapter binding passes the complete formal model
   qualification suite and a fresh hosted app-build acceptance workflow.
2. An operational signed catalog contains at least one useful, current, qualified plugin and has
   publisher revocation, expiry, digest pinning, transparency, and rollback behavior.
3. The authenticated browser application supports catalog discovery, permission and qualification
   review, disabled-by-default installation, explicit enablement, health diagnosis, disablement,
   rollback, and uninstall without accepting arbitrary filesystem paths.
4. Upgrade and rollback pass hosted acceptance from the preceding supported release, preserving
   configuration, plugin state, checkpoints, and evidence.
5. Security, dependency, schema, unit, contract, integration, browser, clean-wheel, container,
   qualification, secret-scan, provenance, and evidence gates pass on the Beta commit.

Privileged WMS, ERP, broker, cloud, HPC, GPU, and physical-QPU connectors do not become trusted
merely because RAD Agent reaches Beta. Each remains unavailable until its own adapter, permissions,
benchmarks, failure behavior, and real-environment qualification pass.

## Current result

Alpha 4 improves the local plugin journey with verified pre-install inspection, explicit
install-and-enable, truthful execution status, and runtime diagnostics. Beta promotion is **not yet
earned** because the real-model and operational public-catalog gates above are still open.
