# Proxy Allowlist — Staging Machine / RHOSP-Agent VM

This list covers hosts needed to download model weights, Python packages, and
container images - whether that's happening on a separate **internet-connected
staging machine** (see [README.md](README.md) step 3's fallback path) before an
offline transfer, or directly on the **RHOSP-Agent VM itself** if it has
proxied/temporary outbound access (the preferred path in step 3/4). If the VM is
genuinely airgapped with zero outbound access, none of this applies to it - only
to the staging machine.

All entries are outbound **HTTPS (443)** unless noted otherwise.

## Hugging Face — model weights

| Host | Why |
|---|---|
| `huggingface.co` | Hub API, model card metadata, auth |
| `*.huggingface.co` | LFS CDN edge hosts actual weight bytes stream from (`cdn-lfs.huggingface.co`, `cdn-lfs-us-1.huggingface.co`, `cdn-lfs-eu-1.huggingface.co`, etc.) |
| `hf.co` / `*.hf.co` | Short-link domain HF sometimes redirects through |

If the proxy can't do wildcard rules, allow the exact hosts above and watch the
proxy's deny log during a first test download — Hugging Face occasionally routes a
file through a CDN host not in this list; the log shows exactly which one got blocked.

## PyPI — Python packages (`huggingface_hub`, `vllm`, `fastapi`, `openstacksdk`, etc.)

| Host | Why |
|---|---|
| `pypi.org` | Package index / metadata |
| `files.pythonhosted.org` | Actual package downloads |

## Docker Hub — base images (e.g. `python:3.12-slim`, `vllm/vllm-openai`)

| Host | Why |
|---|---|
| `registry-1.docker.io` | Image layer pulls |
| `auth.docker.io` | Registry auth tokens |
| `index.docker.io` | Registry index |
| `production.cloudflare.docker.com` | CDN backing layer downloads |

## GitHub Container Registry — Open WebUI image

| Host | Why |
|---|---|
| `ghcr.io` | Registry API |
| `pkg-containers.githubusercontent.com` | Actual image layer downloads |

## GitHub — this repo, `git`/`gh` operations

| Host | Why |
|---|---|
| `github.com` | Web/API, `git` over HTTPS |
| `codeload.github.com` | Tarball/zip downloads |
| `raw.githubusercontent.com` | Raw file fetches |
| `objects.githubusercontent.com` | Release asset / LFS downloads |
| `api.github.com` | Only needed if using the `gh` CLI |

## NVIDIA — only if also staging CUDA/driver/container-toolkit installers from this machine

| Host | Why |
|---|---|
| `developer.download.nvidia.com` | CUDA toolkit, driver installers |
| `nvidia.github.io` | `nvidia-container-toolkit` apt/yum repo |

## Debian/Ubuntu package mirrors — needed on the RHOSP-Agent VM itself

Needed for `docker compose build` (the `tool-server` image installs `gcc`/
`python3-dev` via apt to compile `netifaces`, a transitive `openstacksdk`
dependency with no prebuilt wheel for every Python version) and for any other
`apt install` on the VM (e.g. `docker-compose-plugin` via apt instead of the
GitHub binary).

| Host | Why |
|---|---|
| `deb.debian.org` | Debian package mirror - the `python:3.12-slim` base image's apt sources |
| `security.debian.org` | Debian security updates mirror |
| `archive.ubuntu.com` | Ubuntu package mirror - the VM's own OS (Ubuntu 24.04) |
| `security.ubuntu.com` | Ubuntu security updates mirror |
| `download.docker.com` | Docker's official apt repo, only if installing `docker-compose-plugin` via apt rather than the GitHub release binary |
