# Component AE Evidence: RW-100K Reference Workflow

Date: 2026-08-12 | Outcome: TESTED

The qualification fixture contained exactly 100,000 data rows. Its SHA-256 digest was
`sha256:e856ce1f1ac48286d63de4a928150b4db1ad7c71a65bcd524cac22ddd14be2bc`.
The deterministic table digest was
`sha256:367dee6ba37be43a6ccd3b755821aac90a237f15097182e950947843a50d9ba2`.
The verified seven-record evidence head was
`sha256:bd983a70c333fbf59c71c844a00b1d01ff2449ba573abb7a105c70cdb90278d1`.

Qualification environment: Linux 6.18.35 x86_64 with glibc 2.39; Python 3.12.13. One
`time.perf_counter` run measured deterministic fixture generation plus in-memory CSV import
at 0.2773 seconds and the workflow through explanation at 0.6334 seconds. These figures are
descriptive evidence for this run only. Browser runtime was absent and no virtual-grid or
sub-two-second browser-render claim is made.

Verified: 275 tests; exact fixture count/schema; quality/statistics/chart/explanation
digests; atomic save/reopen; mutation and replay rejection; complete evidence-chain and
JSON/Markdown reports; Ruff; strict mypy; schema/contracts; builds; and fresh-wheel smoke.
