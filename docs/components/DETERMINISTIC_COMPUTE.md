# Component AA: Deterministic Compute Service

Status: TESTED | Boundary contract: 1.0

`DeterministicCompute` is a provider-independent, dependency-free calculation boundary.
It loads bounded caller-supplied UTF-8 CSV bytes, infers a strict tabular schema, computes
summary statistics, performs projection and stable sorting, and produces validated chart
inputs. It performs no file, workspace, network, provider, or credential access.

Every operation returns engine/version identity, input and output SHA-256 digests,
canonical parameters, and an explicit seed field. Outputs are immutable after digesting.
The current operations are deterministic and therefore record `seed=None`; future
stochastic scientific algorithms must accept and record an explicit seed.

CSV loading is currently bounded to 256 MiB, 1,000,000 rows, and 1,024 columns, but the
parsed table is held in memory. This supports the later 100K reference workflow but does
not claim out-of-core execution, econometrics, numerical solvers, joins, aggregations,
chart rendering, or benchmark qualification. Those capabilities require separately
specified and tested extensions.
