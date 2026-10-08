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
