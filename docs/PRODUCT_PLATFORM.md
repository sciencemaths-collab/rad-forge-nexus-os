# RAD Industrial Product Map

RAD is the governed control plane shared by installable domain products. Each product must declare
its exact input contract, capability version, qualification scope, approvals, external effects,
acceptance checks, and downloadable evidence. Presence in a repository is not availability.

| Product | First installable outcome | Qualified today | Deliberately unavailable |
|---|---|---|---|
| RAD Agent / Forge Runtime | Plan, approve, execute bounded tools, verify, and audit | Local governed agent, typed capabilities, pre-install plugin review, signed lifecycle, activation diagnostics, and no-host-import WebAssembly execution | Public marketplace, browser plugin installation, and privileged plugin host interfaces |
| RAD Compute Engine / vQPU | Route exact workloads to qualified compute | Local CPU quantum simulation; Apple Metal float32 matrix multiplication | NVIDIA, Slurm, AWS batch, and physical QPU execution |
| RAD Optimization Engine / PathWoven | Solve bounded optimization contracts | Five packaged continuous benchmark objectives | General warehouse, routing, scheduling, discrete, and mixed-variable claims |
| RAD Decision Engine / Financial | Produce reviewable capital recommendations | Operator-supplied bounded snapshots; no transactions | Broker execution and unqualified live market connectors |
| RAD Warehouse Operations | Recommend priority inventory picks | Bounded integer single-SKU allocation with distance cost | WMS/ERP writes, routing, labor, and replenishment |

## Plugin delivery roadmap

The local installer now provides a signed package format, configured publisher identity,
compatibility checks, exact permission review, install/enable/disable/uninstall lifecycle,
qualification digest binding, side-by-side versions, audit events, and rollback. Packages remain
inert until explicitly enabled and qualified. Qualified zero-permission `wasm-v1` plugins can run
through RAD Node. Operators can inspect exact authority before installation, explicitly combine
installation with activation, and diagnose every enabled adapter. Privileged host interfaces, a
signed public catalog, and browser installation require additional implementation and qualification.

Until those controls exist, integrations are installed as pinned Python distributions or source
revisions, registered explicitly by an operator, and remain fail-closed when their exact
qualification is absent.
