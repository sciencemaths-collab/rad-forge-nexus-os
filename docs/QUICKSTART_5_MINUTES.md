# RAD Agent: Five-Minute Quick Start

This starts RAD Agent with a local Ollama or LM Studio model. It requires Python 3.12+, `pipx`,
and a running local model server.

## 1. Install

```bash
pipx install nexus-os==0.2.0a2
rad --help
```

Until the package is available from PyPI, install the attested wheel downloaded from the
GitHub release after verifying it against `SHA256SUMS`:

```bash
pipx install ./nexus_os-0.2.0a2-py3-none-any.whl
```

## 2. Configure and verify

Start Ollama or LM Studio, then run:

```bash
rad setup
rad models list
rad models test
rad doctor
```

Setup detects common loopback endpoints and creates private files under `.rad-agent/`. The
default is visibly unqualified development mode: planning and review only, without tool
execution.

## 3. Start

```bash
rad serve
```

Open <http://127.0.0.1:8765>, log in with the operator password created during setup, choose
app creation, research, or data analysis, submit an objective, review the proposed plan, and
approve only the exact plan you intend to run.

Qualified execution additionally requires an independently attested model binding. See
[Using RAD Agent](USING_RAD_AGENT.md) for provider setup and the approval/execution workflow.
