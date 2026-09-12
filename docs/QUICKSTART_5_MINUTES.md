# RAD Agent: Five-Minute Quick Start

This starts RAD Agent with a local Ollama or LM Studio model. It requires Python 3.12+,
[`pipx`](https://pipx.pypa.io/stable/installation/), and a running local model server.

## 1. Install

RAD Agent is not published on PyPI. Download the signed Alpha 4 wheel, checksum file, and
evidence archive from the [GitHub release](https://github.com/sciencemaths-collab/rad-forge-nexus-os/releases/tag/v0.2.0a10):

```bash
mkdir -p dist
gh release download v0.2.0a10 --repo sciencemaths-collab/rad-forge-nexus-os --dir dist
sha256sum --check dist/SHA256SUMS --ignore-missing
gh attestation verify dist/nexus_os-0.2.0a10-py3-none-any.whl \
  --repo sciencemaths-collab/rad-forge-nexus-os
pipx install ./dist/nexus_os-0.2.0a10-py3-none-any.whl
rad --version
rad --help
```

On macOS, run `shasum -a 256 -c dist/SHA256SUMS` from the directory containing `dist/`.
Checksum entries use portable base filenames. Run the checksum command from the directory shown
above so the downloaded artifacts are verified before installation.

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

## Container image

The versioned multi-architecture image is published without a moving `latest` tag. Pin the
version or, preferably, the verified manifest digest shown on the
[package page](https://github.com/sciencemaths-collab/rad-forge-nexus-os/pkgs/container/rad-agent):

```bash
docker pull ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10
docker run --rm ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10 --version
```

The browser application and model endpoint are loopback-only. Running them from the image
therefore requires host networking, which is directly supported on Linux and must be enabled
in compatible Docker Desktop versions. Persist configuration and workspace data explicitly:

```bash
mkdir -p rad-data
docker run --rm -it --network host \
  -v "$PWD/rad-data:/workspace" \
  ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10 \
  setup --config-dir /workspace/.rad-agent \
  --provider ollama --base-url http://127.0.0.1:11434/v1 --model YOUR_MODEL_ID

docker run --rm -it --network host \
  -v "$PWD/rad-data:/workspace" \
  ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10 \
  serve --config-dir /workspace/.rad-agent
```

If host networking is unavailable, use the wheel installation. Do not expose RAD Agent or an
unauthenticated model server on a public interface.
