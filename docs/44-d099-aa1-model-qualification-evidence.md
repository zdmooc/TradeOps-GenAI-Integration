# D099 AA1 — model qualification evidence contract

`scripts/d099_aa1_qualification.py` is **read-only and offline**.
Its JSON input fields must come from an independently reviewed run on
the actual HP workstation: pinned model digest, approved local Ollama
endpoint, declared and empirically exercised context size, observed
peak process memory/host memory and latency, OpenCode structured response,
and **tool-side** deny trace (not model narrative refusal).

The original `qwen2.5:3b` advertised 32,768 context, below the
65,536-token AA1 target, and failed source-grounded architecture analysis;
do not mark AA1 closed because its transport/JSON smoke succeeded.
The script deliberately does not download/install any model, inspect
private logs, run OpenCode, call HTTP, or mutate CRC.

A synthetically complete measurement dictionary can at most return
`AA1_EVIDENCE_REVIEW_READY`. It **never** returns
`AA1_LOCAL_MODEL_BASELINE_VALIDATED=true` since signatures, host
attestation and security boundaries require independent human review.

After the owner selects an appropriate engine and explicitly captures
measurement data in a local file (do not commit local diagnostics):

```bash
python scripts/d099_aa1_qualification.py --measurements path/to/local.json
```

Do not invent `observed_context_tokens` from `ollama show`.
`DENY_WITH_EXTERNAL_TRACE` requires an independent host/runtime tool
authorization audit, not a model's statement.
