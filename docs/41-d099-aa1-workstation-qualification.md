# D-099 AA1 — workstation evidence capture (user-executed)

Precondition: local isolated workdir `/c/workspaces/D099-AA1-OPENCODE-SANDBOX`, existing deny-all `OPENCODE_CONFIG_CONTENT`, provider `ollama/qwen2.5:3b`. No automatic permission widening, package installation, model pull, cluster operation or Git merge.

## 1. Resolved-policy audit — read-only

Once PR #25 is checked out in `/c/workspaces/TradeOps-D099-AA1`:

```bash
cd /c/workspaces/D099-AA1-OPENCODE-SANDBOX
opencode debug agent plan |
  python /c/workspaces/TradeOps-D099-AA1/scripts/d099_aa1_policy_check.py
```

The checker outputs `POLICY_RESOLVED_PASS` only if it sees a final blanket `* deny` and conservative samples of bash, edit, read, external directory and webfetch all resolve to deny. `runtime_denial_proven=false` even on PASS. It consumes full agent debug JSON **from stdin only** and prints aggregated decisions, not secrets, paths, tokens, or raw policy content. If any rule is malformed, or the final catch-all is absent, it fails closed.

An external OpenCode permission system / runtime trace (not a model self-report) is still required to promote `AA1_RUNTIME_DENIAL_PROVEN`. A missing tool event plus narrative refusal is insufficient.

## 2. Resource snapshot — read-only, measured on Windows

In a fresh **PowerShell** window while a supervised one-turn OpenCode run is executing in Git Bash (do NOT paste into Git Bash):

```powershell
Get-CimInstance Win32_OperatingSystem |
  Select-Object TotalVisibleMemorySize, FreePhysicalMemory
Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessName -match 'ollama|opencode' } |
  Select-Object ProcessName, Id, CPU, WorkingSet64
```

`WorkingSet64` is process working-set memory in bytes and is not total runtime/system memory. Multiple snapshots while the run is active improve accuracy. A single snapshot after completion is not a peak measurement. Never report hypothetical peak CPU/RAM as observed.

## 3. 32k context, 64k criterion

`ollama show qwen2.5:3b` advertised 32,768 context. The candidate is **NOT QUALIFIED** for a >=64k acceptance criterion. Do not override it in config to claim higher context, and do not install a larger model while sharing a 24 GiB-class host with CRC. A chunked/retrieval approach can later be evaluated as a separate architectural option, without calling it 64k model-context proof.

No D-099 runtime touches OpenShift or changes TradeOps PARK.

## AA1 policy diagnostic — workstation returned targeted DENY but global check failed

Observed on HP17G3 worktree `db1233c` (operator log): `bash=deny*3`, `edit=deny*3`, `external_directory=deny*2`, `read=deny*2`, `webfetch=deny*2` (12 sampled checks). Previous checker returned `status=FAIL` solely because its **literal last rule** test returned `terminal_deny_all=false`. This does **not** prove that OpenCode actually allowed an unsafe operation. The earlier filtered rule sequence ended in `* deny`, but the complete resolved policy evidently includes other entries that this filter hid.

The revised checker follows documented last-match semantics: a blanket `* deny` followed only by **more deny rules** remains globally restrictive; a later `allow` or `ask` on **any** category prevents a global deny claim, even if the 12 sampled checks remain denied. It reports how many potentially relaxing entries occur after the last blanket deny, with only sanitized permission category names — never their path patterns.

Expected statuses:

- `POLICY_RESOLVED_PASS`: final effective blanket deny not relaxed by later entries, and sampled probes denied; **not** runtime enforcement proof.
- `TARGETED_DENY_PASS_GLOBAL_UNVERIFIED`: sampled denials all hold but a possible late exception (or no blanket denial) leaves untested capabilities.
- `FAIL`: malformed config or at least one unsafe sampled result.

Rerun from sandbox after fetching updated PR #25:

```bash
opencode debug agent plan |
  python /c/workspaces/TradeOps-D099-AA1/scripts/d099_aa1_policy_check.py
```

If status stays `TARGETED_DENY_PASS_GLOBAL_UNVERIFIED`, send the sanitized `reopening_categories`, `allow_or_ask_after_blanket`, and `rules_after_blanket` fields; do **not** disclose raw patterns or full config. Never change the deny-all profile to force a PASS, and never use `--auto`. A tool-side denial event is still a separate proof.
