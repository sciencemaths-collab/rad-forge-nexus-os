# RAD Compute Engine

Status: CPU AND APPLE METAL BACKENDS QUALIFIED | Boundary contract: 1.0

vQPU 0.5.0 provides the first qualified compute backend through capability
`rad.compute.local`. RAD exposes only `compute.execute` for the qualified local CPU quantum
simulator.

vQPU 0.6.0 adds capability `rad.compute.apple_gpu` through adapter 1.0.0 and the exact backend
`apple.metal.mlx`. Its formal qualification used MLX 0.32.2 on a real Apple Silicon Metal GPU and
passed 15 of 15 bounded float32 matrix-multiplication cases with deterministic byte-for-byte
replay, NumPy reference agreement, `simulated=false`, zero observed numerical error, denied
network access, and denied fallback. RAD exposes this backend only as `compute.matmul`, with
approval and exact qualification required.

Install the hardware runtime from the pinned vQPU source revision on Apple Silicon:

```bash
python -m pip install \
  'vqpu-sdk[apple] @ git+https://github.com/sciencemaths-collab/vqpu.git@4a320689ddbcf14cbadc78d56c67550c45c24567'
```

The RAD Linux container cannot execute Apple Metal. It keeps the backend unavailable instead of
falling back to CPU. HPC schedulers, cloud batch systems, and physical QPUs are inventoried by
vQPU but remain explicitly unqualified and unroutable until a real target is available for a
separate benchmark and exact attestation. No credentials are discovered, stored, or inferred.
