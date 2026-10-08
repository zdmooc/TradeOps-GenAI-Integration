# D-099 AA1 — OpenCode + Ollama local baseline

Status: **PREPARATION_ONLY / LOCAL_RUNTIME_PENDING**. This is not a deployed policy gateway, nor a model benchmark. Reuses TradeOps' existing D-090 Ollama boundary; does not change it.

## Scope and safety

The script `scripts/d099_aa1_local_preflight.sh` only reads CLI versions, Ollama HTTP API version and installed model names. No install, no auto-download, no container start, no OpenShift changes, no TradeOps un-PARK, no Git push. It does not print environment variables, tokens, kubeconfig or authenticated headers.

## Run on the HP ZBook Windows 11 — Git Bash

**Repository:** `TradeOps-GenAI-Integration`  
**Directory:** `/c/workspaces/TradeOps-GenAI-Integration`  
**Branch:** after review/merge; or use the D-099 PR branch explicitly  
**Precondition:** existing OpenCode CLI and Ollama daemon on `127.0.0.1:11434`; no install in this procedure.  
**Command:**

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
bash scripts/d099_aa1_local_preflight.sh
```

**PASS marker:** `D099_AA1_PREFLIGHT_PASS`; this does **not** close AA1. If a tool/server is unavailable, return failure without claiming a model test. **Runtime impact:** reads on Windows only; CRC unchanged. **Rollback:** none needed; no mutation.

## Separate supervised inference (do not run automatically)

Only after verifying an installed model and inspecting local OpenCode permissions, use a scratch workspace and a read-only `plan` agent with no GitHub credentials or tools capable of write; independently check that the selected model supports the context window demanded by OpenCode. An illustrative command is:

```bash
# Run only inside a user-created isolated scratch directory with tested deny-edit/bash policy:
opencode run --model 'ollama/<installed-model>' --agent plan 'Reply ONLY with JSON: {"ok":true,"purpose":"local-smoke"}'
```

Replace the placeholder with an actual installed model. Do not infer safety from a prompt alone. Capture non-sensitive version/model digest, prompt and config hash, response JSON validity, elapsed time, CPU/RAM, errors, timeout and recovery; redact output. The baseline stays `LOCAL_MODEL_BASELINE_VALIDATED=NO` without a real execution log and permission tests.

## Source compatibility

OpenCode official provider/CLI documentation describes `opencode run --model provider/model` and local Ollama at `localhost:11434/v1`. Ollama documents `ollama launch opencode`; this procedure does not launch it automatically or change global config. Model/context compatibility must be independently measured on this 24 GiB-class workstation.

## No claims

Preflight PASS != Ollama inference PASS != OpenCode run PASS != local model qualification != AA2 enforceable least privilege != AA8 CRC proof.

## Optional read-only local-model JSON qualification

This is a separate *explicit opt-in* test. It calls only `http://127.0.0.1:11434/api/tags` and `/api/generate` for an **already installed local** model (no `:cloud` model). It does not read repositories, install software, run OpenCode, or alter CRC. It briefly consumes workstation CPU/RAM during local inference; don't run concurrently with a high-load CRC session. Uses a bounded prompt and 80 output tokens. It captures model digest, local latency, token count, response hash (not response content), and marks host CPU/RAM measurements as NOT_MEASURED.

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
ollama list  # choose one ALREADY installed local model
D099_ALLOW_LOCAL_INFERENCE=YES python scripts/d099_aa1_ollama_smoke.py --model 'EXACT_MODEL_NAME'
```

Do not copy the example model name literally. Expected JSON status is `LOCAL_JSON_SMOKE_PASS`. Ollama-only JSON proof does **not** validate OpenCode, the mandated 64k+ coding-agent context, CLI permissions or AA1 gate closure. Official Ollama/OpenCode documentation: https://github.com/ollama/ollama/blob/main/docs/integrations/opencode.mdx . OpenCode often needs at least 64k context to work reliably and may exceed available RAM on this workstation; choose a tested model and context deliberately, never claim it is suitable based on preflight alone.

## D-099 HP17G3 observed failure and correction — 2026-10-08

The user observed:
- worktree on PR #25 `71d04df` correct;
- `AA1_MISSING_TOOL=opencode`: OpenCode CLI not available in Git Bash PATH;
- `ollama list` succeeded and showed `qwen2.5:3b`;
- Python JSON smoke failed with `URLError` because the original helper pinned `127.0.0.1:11434` and did not share the Ollama CLI host/proxy behavior; actual cause must be verified locally;
- the attempted `--model 'NOM_EXACT_DU_MODELE'` is a documentation placeholder, not the installed model.

The helper now reads `OLLAMA_HOST` when set, conservatively permits loopback or the known Windows host-only interface `192.168.56.1`, blocks external hosts, bypasses HTTP proxies only for the accepted local endpoint, and prevents HTTP redirects. The preflight uses the *same* API resolver as the JSON smoke.

Read-only diagnostics on Windows Git Bash:

```bash
cd /c/workspaces/TradeOps-D099-AA1
printf 'OLLAMA_HOST=%s\n' "${OLLAMA_HOST:-<unset>}"
curl --noproxy '*' -fsS --max-time 8 http://127.0.0.1:11434/api/version
curl --noproxy '*' -fsS --max-time 8 http://localhost:11434/api/version
# After updating the PR branch:
python scripts/d099_aa1_ollama_smoke.py --probe
```

Use the host shown in `OLLAMA_HOST` only if it is local/authorized. If both `curl` probes fail while `ollama list` succeeds, compare the CLI's `OLLAMA_HOST` with this script and investigate Windows listener, `HTTP_PROXY` or security filtering. Do not set the server to `0.0.0.0` just to bypass these diagnostics.

For OpenCode stable CLI, official installation options include `npm install -g opencode-ai`; this is a workstation change requiring operator action, not an automatic D-099 step. Verify `node --version`, `npm --version`, `opencode --version`.

Correct optional model command: `D099_ALLOW_LOCAL_INFERENCE=YES python scripts/d099_aa1_ollama_smoke.py --model qwen2.5:3b`. Do not run until a read-only API probe works. **Even with PASS**, OpenCode performance and policy gating remain NOT TESTED.

## HP17G3 — local Ollama PASS and OpenCode next step (2026-10-08)

Observed in the **user's Windows Git Bash**, not GitHub CI: Ollama API probe PASS on `192.168.56.1:11434` (not localhost/loopback), OpenCode 1.18.35 CLI reports a version after npm install, local `qwen2.5:3b` JSON smoke `LOCAL_JSON_SMOKE_PASS` in 10917 ms; digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`. Source is an operator-pasted terminal transcript; retained in governance PR #16. No CPU/RAM measurements, no OpenCode model turn, no 64k-context proof, and no permission denial evidence. npm noted its install `postinstall` script was not in the allowed scripts list, so do **not** assume the installed CLI is fully functional.

### Next supervised qualification (dedicated scratch directory, no Git repo)

1. From Git Bash, run `ollama show qwen2.5:3b` (read-only model metadata) and `opencode run --help` (CLI option discovery). Do not download or change the model.
2. Create a non-repository folder, separate from `/c/workspaces/TradeOps-GenAI-Integration`, with **no secrets, GitHub tokens or kubeconfig**.
3. For this one smoke only, set **inline OpenCode config** via `OPENCODE_CONFIG_CONTENT` to explicitly select the single local provider, point to the API that actually responded, disable all tool permissions, disable sharing and autoupdates. `OPENCODE_CONFIG_CONTENT` overrides per-project config on OpenCode 1.x; inspect `opencode models ollama` before a model turn.

```bash
mkdir -p /c/workspaces/D099-AA1-OPENCODE-SANDBOX
cd /c/workspaces/D099-AA1-OPENCODE-SANDBOX
export OPENCODE_DISABLE_AUTOUPDATE=1
export OPENCODE_DISABLE_DEFAULT_PLUGINS=1
export OPENCODE_DISABLE_LSP_DOWNLOAD=1
export OPENCODE_DISABLE_CLAUDE_CODE=1
export OPENCODE_CONFIG_CONTENT='{
  "$schema":"https://opencode.ai/config.json",
  "model":"ollama/qwen2.5:3b",
  "enabled_providers":["ollama"],
  "provider":{
    "ollama":{
      "npm":"@ai-sdk/openai-compatible",
      "name":"Ollama Local",
      "options":{"baseURL":"http://192.168.56.1:11434/v1"},
      "models":{"qwen2.5:3b":{"name":"Qwen 2.5 3B"}}
    }
  },
  "permission":{"*":"deny","bash":"deny","edit":"deny","external_directory":"deny"},
  "agent":{"plan":{"permission":{"*":"deny"}}},
  "share":"disabled",
  "autoupdate":false,
  "snapshot":false
}'
opencode models ollama
# STOP if ollama/qwen2.5:3b is absent or config/tool enforcement is uncertain
opencode run --model ollama/qwen2.5:3b --agent plan \
  'Respond with exactly AA1_OPENCODE_LOCAL_OK and do not use tools.'
```

This is a **model round-trip only**, not a proof that the permission layer denies malicious calls. If OpenCode fails or tries to download extra packages, capture the error and STOP; review Node's npm allow-scripts warning and local OpenCode config, do not grant scripts or wider tool permission automatically. If a model succeeds, also capture console timings and Windows CPU/RAM externally. See official [OpenCode provider documentation](https://docs.opencode.ai/docs/providers/), [OpenCode permissions](https://opencode.ai/docs/permissions/), [OpenCode CLI](https://opencode.ai/docs/cli/) and [Ollama integration](https://github.com/ollama/ollama/blob/main/docs/integrations/opencode.mdx).

A 3B Ollama model completing one text prompt **does not** qualify OpenCode coding-agent throughput, context length, security or all AA1 acceptance gates. If it advertises an insufficient context or cannot work under the 24GiB workstation constraint, report `AA1_CONTEXT_UNQUALIFIED` rather than pull a larger model automatically.
