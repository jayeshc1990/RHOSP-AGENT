# RHOSP Agent

A read-only, natural-language query agent over multiple airgapped RHOSP16/17/18
clouds. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design rationale.

Stack: **Open WebUI** (chat UI) + a small **FastAPI tool server** (read-only
OpenStack queries, this repo's `tool_server/`) + a self-hosted LLM served by
**vLLM** on the GPU VM.

## 0. Prerequisites on RHOSP-Agent VM

- Docker or Podman + compose plugin
- NVIDIA driver + CUDA + `nvidia-container-toolkit` for GPU passthrough to containers
  (only needed if you containerize vLLM; running vLLM directly on the host also works
  and is what this README assumes)
- Check your GPU memory before picking a model:
  ```bash
  nvidia-smi --query-gpu=name,memory.total --format=csv
  ```
  40GB and 80GB A100 variants exist - this determines which model tier to run (step 3).

## 1. Create a read-only application credential on each cloud

Do this against **each** RHOSP cloud you want the agent to query, as a user who
already has the `reader` role available (RHOSP16+ ships OpenStack's secure RBAC
`admin`/`member`/`reader` roles; confirm they're enabled on your deployment -
check `policy.yaml` overrides applied via director if a service doesn't seem to
recognize `reader`).

```bash
# Authenticate as an existing user who can grant roles, targeting the scope
# you want the agent to see. For cloud-wide read visibility, use system scope:
openstack role add --user <agent-service-user> --user-domain Default \
  --system all reader

# Then create a scoped application credential for that user - this is what
# actually goes into clouds.yaml, never the user's own password:
openstack application credential create rhosp-agent-ro \
  --description "RHOSP Agent - read only, do not expand roles"
```

The command prints an `id` and `secret` - copy both into `clouds.yaml` (see below).
Application credentials can be revoked independently of the user's password:
`openstack application credential delete <id>` if you ever need to cut off access.

**Verify the restriction actually works** before trusting it:
```bash
openstack --os-cloud rhosp16-site-a server list        # should succeed
openstack --os-cloud rhosp16-site-a server create foo ...  # should 403
```

## 2. Configure clouds.yaml

```bash
cp clouds.yaml.example clouds.yaml
```
Fill in `auth_url`, `application_credential_id`, `application_credential_secret`,
`region_name`, and `cacert` for each cloud. `clouds.yaml` is gitignored - never commit it.

## 3. Get a model onto the airgapped VM

Pick a tier based on the VRAM you checked in step 0. This workload (NL → a
structured tool call → phrase a JSON result) does not need a 70B-class model -
start small:

| GPU | Model |
|---|---|
| A100 40GB | `Qwen/Qwen2.5-14B-Instruct` or `meta-llama/Llama-3.1-8B-Instruct` |
| A100 80GB | `Qwen/Qwen2.5-32B-Instruct`, or a 4-bit AWQ build of `Llama-3.1-70B-Instruct` if the smaller tier's tool-selection accuracy isn't good enough in testing |

On an internet-connected machine:
```bash
pip install "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen2.5-14B-Instruct --local-dir ./qwen2.5-14b-instruct
```
(Gated repos like Llama require accepting the license on huggingface.co first.)

Verify the download, tar it, and transfer it to the VM via your approved
offline-media process. Also bring across an offline wheelhouse for `vllm` and
its dependencies if the VM has no internal PyPI mirror.

### If you have internet on a staging machine: build the vLLM wheelhouse

**Don't** just run `pip download vllm -d ./vllm-wheelhouse` on its own - it
reliably misses transitive dependencies that are gated by platform markers
(e.g. `llguidance`), which then fail on the airgapped VM with "no matching
distribution found" one package at a time. The robust way is to actually
**resolve and install vLLM for real** in an environment matching the VM
(Python 3.12, Linux x86_64), then download exactly what that real install
resolved to:

```bash
mkdir -p vllm-wheelhouse-build && cd vllm-wheelhouse-build
docker run --rm -v "$PWD:/out" python:3.12-slim bash -c "
  pip install --upgrade pip -q &&
  pip install vllm -q &&
  pip freeze > /out/vllm-frozen-requirements.txt &&
  mkdir -p /out/vllm-wheelhouse &&
  pip download -r /out/vllm-frozen-requirements.txt --only-binary=:all: -d /out/vllm-wheelhouse &&
  echo DONE
"
tar -czf vllm-wheelhouse-complete.tar.gz vllm-wheelhouse
```

This needs no GPU (it only resolves and downloads packages, never runs them).
Expect several GB - PyTorch and its bundled CUDA runtime libraries dominate
the size. Match the Python version (`python3 --version` on the target VM) if
it differs from 3.12.

**No Docker on the staging machine?** Use WSL2 instead for the same effect:
```bash
wsl --install -d Ubuntu-24.04
```
then inside WSL:
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv
python3.12 -m venv ~/v && source ~/v/bin/activate
pip install --upgrade pip -q && pip install vllm -q
pip freeze > ~/frozen.txt
mkdir -p ~/vllm-wheelhouse
pip download -r ~/frozen.txt --only-binary=:all: -d ~/vllm-wheelhouse
tar -czf ~/vllm-wheelhouse-complete.tar.gz -C ~ vllm-wheelhouse
```
(grab the result from `\\wsl$\Ubuntu-24.04\home\<user>\` in Windows Explorer)

Transfer `vllm-wheelhouse-complete.tar.gz` to the VM the same way as the model,
via your approved offline-media process - see the proxy hosts you'll need on
the staging machine's network in [PROXY_ALLOWLIST.md](PROXY_ALLOWLIST.md).

## 4. Serve the model with vLLM

On the VM:
```bash
pip install --no-index --find-links ./vllm-wheelhouse vllm   # or from an internal mirror
vllm serve /path/to/qwen2.5-14b-instruct \
  --max-model-len 8192 \
  --api-key local-key
```
This exposes an OpenAI-compatible API on `http://localhost:8000/v1` with native
tool/function-calling support. Smoke-test before wiring up the UI:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer local-key" -H "Content-Type: application/json" \
  -d '{"model": "/path/to/qwen2.5-14b-instruct", "messages": [{"role": "user", "content": "hello"}]}'
```

## 5. Run the tool server + Open WebUI

```bash
docker compose up -d --build
```
This starts:
- `tool-server` on `:8080` - your read-only OpenStack query API (serves an
  OpenAPI spec at `/openapi.json`)
- `open-webui` on `:3000`, pointed at the vLLM endpoint from step 4

## 6. Wire it together in Open WebUI

1. Open `http://<vm>:3000`, create the first (admin) account.
2. Admin Settings → Connections: confirm the OpenAI-compatible connection
   points at `http://host.docker.internal:8000/v1` (already set via the
   compose env var) and the model you served is selectable.
3. Admin Settings → Tools → add an OpenAPI tool server at
   `http://tool-server:8080/openapi.json` (or `http://<vm-ip>:8080/openapi.json`
   if not on the same Docker network).
4. Create a Model preset (Workspace → Models) that: uses the vLLM model,
   has the tool server enabled, and has the contents of
   [system_prompt.md](system_prompt.md) pasted in as its system prompt.
5. Chat against that model preset.

## 7. Validate before rolling out

- Ask it to list VMs, filter by flavor, count resources, and query a specific
  cloud by name - confirm counts from `analyze` match `openstack ... list | wc -l`.
- Try to get it to do something destructive ("delete this VM", "reboot server X",
  "create a network") and confirm it refuses - there is no tool for it to call.
- Confirm the application credential really is reader-scoped on every cloud
  (step 1's verification), so even a bug here can't mutate anything.

## Extending the tool set

Add new resource types in [tool_server/app/registry.py](tool_server/app/registry.py)
- read that file's docstring first. Only ever add `list`/`get`/`find` methods,
confirmed read-only in the openstacksdk docs.
