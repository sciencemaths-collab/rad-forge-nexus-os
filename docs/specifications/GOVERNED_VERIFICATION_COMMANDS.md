# Governed Verification Commands

Status: implemented for RAD Agent Phase 8D.

## Contract

- Unit, integration, security, and failure-test stages carry deterministic command arrays compiled
  by app-build mode; model output cannot select an executable or add arguments.
- The bundled executor accepts only four exact `python -m pytest -q <test-directory>` forms.
- Pytest is a runtime dependency because the clean installed-wheel environment executes those
  commands with its own interpreter; verification never relies on undeclared developer tooling.
- Each stage is `SENSITIVE` and requires human approval bound to the exact command payload.
- Execution uses the installed Python interpreter directly without a shell and receives a new,
  credential-free environment. Python isolated mode is retained, with only the approved workspace
  root added for normal project imports.
- A Python audit boundary denies network operations, child processes, system commands, and writes
  outside the approved workspace. Temporary files are redirected inside the workspace.
- Each run has a 150-second timeout and a 128-KiB combined-output limit.
- Results record the exact command, exit code, pass state, bounded output, and truncation state in
  the graph-declared artifact. A nonzero exit fails the stage and blocks downstream work.

## Limitations

This Alpha executor supports Python/pytest projects only. It is not an operating-system container
or VM and does not run arbitrary build scripts, npm scripts, shell commands, deployment, or network
operations. Additional runners require separate sandbox qualification.
