# RAD Industrial Product Map

RAD is the governed control plane shared by installable domain products. Each product must declare
its exact input contract, capability version, qualification scope, approvals, external effects,
acceptance checks, and downloadable evidence. Presence in a repository is not availability.

| Product | First installable outcome | Qualified today | Deliberately unavailable |
|---|---|---|---|
| RAD Agent / Forge Runtime | Plan, approve, execute bounded tools, verify, and audit | Local governed agent and typed capability contracts | General plugin marketplace and autonomous permissions |
| RAD Compute Engine / vQPU | Route exact workloads to qualified compute | Local CPU quantum simulation; Apple Metal float32 matrix multiplication | NVIDIA, Slurm, AWS batch, and physical QPU execution |
| RAD Optimization Engine / PathWoven | Solve bounded optimization contracts | Five packaged continuous benchmark objectives | General warehouse, routing, scheduling, discrete, and mixed-variable claims |
| RAD Decision Engine / Financial | Produce reviewable capital recommendations | Operator-supplied bounded snapshots; no transactions | Broker execution and unqualified live market connectors |
| RAD Warehouse Operations | Recommend priority inventory picks | Bounded integer single-SKU allocation with distance cost | WMS/ERP writes, routing, labor, and replenishment |

## Plugin delivery roadmap

The current adapter and capability contracts are an extension boundary, not an end-user plugin
marketplace. Industrial plugin delivery requires, in order: a signed package format; publisher
identity and provenance; compatibility and dependency resolution; explicit permission manifests;
install/update/disable/uninstall lifecycle; isolated secrets; qualification attestations tied to
plugin, adapter, provider, model/backend, and version; revocation; and auditable rollback.

Until those controls exist, integrations are installed as pinned Python distributions or source
revisions, registered explicitly by an operator, and remain fail-closed when their exact
qualification is absent.
