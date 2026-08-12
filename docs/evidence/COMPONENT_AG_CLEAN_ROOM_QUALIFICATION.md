# Component AG Evidence: Clean-Room Qualification

Date: 2026-08-12 | Outcome: QUALIFIED (OWNER APPROVAL PENDING)

The clean-room run created an isolated source snapshot, installed locked Python and TypeScript
dependencies with fresh disposable caches, passed all 15 automated gates, and passed the
independent source/status review with zero findings.

- Full suite: 285 tests
- Snapshot digest: recorded in the generated `clean-room-report.json`
- Automated evidence digest: recorded in the generated `clean-room-report.json`
- Qualification state: `CLEAN_ROOM_QUALIFIED_OWNER_APPROVAL_PENDING`
- Independent review findings: 0
- Owner approved: false
- Release candidate: false

The prior hosted AF workflow's qualification job passed. Its separate GitHub Dependency Review
job could not run for this private repository without a GitHub Advanced Security entitlement;
the repository now uses blocking portable `pip-audit` and `npm audit` gates instead. The updated
hosted workflow must still pass on this Component AG commit before its evidence is considered
hosted-current.
