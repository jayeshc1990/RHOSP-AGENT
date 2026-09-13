# RHOSP Read-Only NL Query Agent — Architecture

## Goal

A ChatGPT-like UI that lets anyone query one or more airgapped RHOSP16/17/18 clouds in
natural language ("list vms", "get vms with flavor m1.small", "count vms by cloud"),
strictly **read-only**. No API call other than GET/list/show may ever be issued.

## VM

- Name: RHOSP-Agent
- 32GB RAM / 8 vCPU / 250GB boot + 1000GB data volume / 1x NVIDIA A100

## Core principle: enforce read-only at the OpenStack layer, not just the app layer

Layered controls, strongest first:

1. **Identity (primary control).** Dedicated Application Credential per cloud, scoped to
   the built-in `reader` role (secure RBAC: `system-reader` / `project-reader` /
   `domain-reader`, available since Ussuri / RHOSP16+). This is enforced per API action
   inside each service's policy engine (Nova/Neutron/Cinder/Glance/Keystone/Heat) — a
   reader-scoped credential gets 403 on any mutating action no matter what the app or
   model attempts. Use `system-reader` scope if the agent must see resources across all
   projects on a cloud.

   ```bash
   openstack role add --user svc-agent-reader --project <scope> reader
   openstack application credential create agent-ro --role reader \
     --description "RHOSP Agent - read only"
   ```

2. **App / tool layer.** Only implement list/show wrappers over `openstacksdk`. Never
   import or wire a create/update/delete method — there is nothing for the model to
   misuse.

3. **Network (defense-in-depth).** Reverse proxy in front of each cloud's endpoints used
   by the agent, rejecting any HTTP method other than GET/HEAD.

4. **Audit.** Log every NL query → tool call → resulting OpenStack API call with user
   identity and timestamp.

## Architecture

```
Browser -> Chat UI -> Agent Orchestrator -> Tool layer (openstacksdk, reader creds) -> RHOSP clouds (one per site)
                              |
                        Local LLM (vLLM on the A100)
```

## Tool layer (keep it to ~3 tools, not one per API call)

1. `list_resources(cloud, service, resource_type, filters)` — generic wrapper over
   openstacksdk's unified proxies (`conn.compute.servers()`, `conn.network.networks()`,
   `conn.block_storage.volumes()`, `conn.image.images()`, `conn.identity.projects()`,
   etc.), restricted to an explicit allow-list of resource types.
2. `get_resource(cloud, service, resource_type, id)` — the "show" equivalent.
3. `analyze(data_ref, operation)` — deterministic, sandboxed post-processing (pandas)
   for count / filter / group-by / sort / top-N over data already fetched. The model
   emits a structured spec; real code executes it; the exact result is handed back to
   the model for phrasing. Don't ask the LLM to count/filter large JSON by "reading" it.
4. `list_clouds()` — lets the model (and UI cloud-selector) disambiguate which cloud(s)
   a query targets. Every call to (1)/(2) requires an explicit `cloud` argument.

## UI / orchestration options

- **Fast path:** Open WebUI (self-hosted, MIT, works fully offline) + its Tools
  framework, pointed at a local OpenAI-compatible endpoint. Recommended starting point.
- **More control:** custom FastAPI backend + React/Streamlit frontend, LangGraph or a
  hand-rolled tool-calling loop, or an MCP server exposing the 3 tools. Worth it once
  SSO/LDAP integration or per-team cloud access control is needed.

## LLM serving (airgapped)

Serve via **vLLM** (OpenAI-compatible `/v1/chat/completions`, native tool-calling).

Model tier depends on A100 VRAM (40GB vs 80GB — TBD):

| GPU | Model |
|---|---|
| A100 40GB | Qwen2.5-14B-Instruct or Llama-3.1-8B-Instruct |
| A100 80GB | Qwen2.5-32B-Instruct or Llama-3.1-70B-Instruct-AWQ (4-bit) |

This task (NL → structured tool call → phrase JSON result) does not require a 70B-class
model; start small (8-14B) and only move up if tool-selection accuracy is insufficient
in testing.

### Getting a model into the airgapped environment

1. On an internet-connected machine:
   `pip install "huggingface_hub[cli]"` then
   `huggingface-cli download <org>/<model> --local-dir ./model` (accept license terms
   on HF first for gated repos, e.g. Llama).
2. Verify file hashes against the HF repo listing; tar the directory.
3. Transfer via approved offline-media process to the RHOSP-Agent VM.
4. On the VM: confirm NVIDIA driver + CUDA (`nvidia-smi`); install `vllm` from an
   internal mirror or an offline wheelhouse brought across in the same transfer.
5. Serve: `vllm serve /path/to/model --max-model-len 8192 --api-key <local-key>`.
6. Smoke-test tool-calling via `curl` before wiring up the OpenStack tools.

## Build phases

1. Identity: reader-scoped application credentials per cloud; prove writes 403.
2. Inference: vLLM + chosen model running on the VM, tool-calling validated.
3. Tool layer: `list_resources` / `get_resource` / `analyze` / `list_clouds` against
   `openstacksdk`, backed by a multi-cloud `clouds.yaml`.
4. Orchestration + UI: wire chosen UI to local LLM + tools; system prompt constrains
   the model to only use provided tools and always resolve target cloud(s) first.
5. Hardening: GET-only egress proxy, audit logging, UI auth/access control.
6. Validation: adversarial testing — attempt "delete this VM" / "create a network" via
   the chat and confirm refusal at every layer.

## Open decisions

- A100 VRAM: 40GB or 80GB? (drives model tier choice)
- UI: Open WebUI (fast) vs custom FastAPI/React (more control, SSO/audit) — can start
  with Open WebUI and revisit.
- Per-team access control: does every user see every cloud, or should cloud visibility
  be scoped per user/team?
