# Component AB: App-Build Mode Pack

Status: TESTED | Boundary contract: 1.0

`AppBuildMode` compiles an already validated `app_build` project configuration into
the shared canonical task graph. It emits the fail-fast engineering sequence:
specification, design, contract tests, implementation, unit tests, integration tests,
security tests, failure tests, and evidence reporting. It does not fork or bypass the
kernel runtime, policy, approval, checkpoint, evidence, or provider boundaries.

Graph identity is deterministically derived from the validated configuration digest and
mode version. Creative stages inherit the bounded project retry count; verification and
evidence stages run once so a failing gate cannot be hidden by automatic repetition. The
final evidence task carries every declared acceptance ID, while contract and evidence
tasks receive the validated descriptions and verifier identifiers.

The compiler rejects other modes and read-only workspaces. It copies no provider binding,
credential reference, secret reference, network allowlist, or cost configuration into task
inputs. This component compiles work only; it does not claim that generated applications
are correct, execute the graph, select providers, approve effects, or qualify a release.
