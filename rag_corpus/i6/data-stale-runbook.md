# Data Staleness Runbook

When market data exceeds the configured freshness threshold, the assessment state becomes DATA_STALE. Do not infer a current market direction from an old event.

Recovery requires a fresh canonical MarketEvent, data-quality acceptance, and a new downstream assessment. Cached narrative context does not make stale price data fresh.
