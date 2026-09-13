# Proxy Allowlist — Staging Machine (Model/Package Downloads)

This list is for the **internet-connected machine** used to download model weights,
Python packages, and container images before transferring them into the airgapped
RHOSP-Agent environment (see [README.md](README.md) step 3). The airgapped VM itself
needs none of this — it never has outbound internet access.

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
