# Fresh-User App-Build Acceptance

Status: implemented for RAD Agent Phase 8E.

## Contract

The release gate must install the built wheel into a clean virtual environment and exercise the
browser application through its public HTTP boundary. A deterministic qualified loopback provider
is used so the test is repeatable and does not misrepresent an external model as validated.

The journey must prove that an ordinary operator can:

1. authenticate and submit an app-build objective;
2. review and approve the exact candidate digest;
3. select an existing bounded workspace;
4. inspect the real project and provide verified source context to later reasoning stages;
5. approve a digest-bound source change and observe the resulting file;
6. separately approve the compiled unit, integration, security, and failure-test commands;
7. reach verified completion with an intact evidence chain and downloadable artifacts.

The source change creates a small Python module. Existing fixture tests in all four supported test
directories import that module and pass only after the approved implementation is present. The
journey must also verify the private rollback record and all four test-result artifacts.

## Boundaries

- No shell, arbitrary command, package installation, network retrieval, deployment, or publication
  is authorized by this acceptance test.
- The provider cannot choose verification commands or bypass an approval.
- The test proves packaged composition and governed behavior, not model intelligence or production
  qualification.
- Live Ollama and LM Studio validation is recorded separately and remains `NOT RUN` when no such
  service is available in the qualification environment.
