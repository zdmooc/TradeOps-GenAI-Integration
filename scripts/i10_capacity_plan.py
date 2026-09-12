#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math


def required_replicas(
    peak_rps: float,
    p95_service_seconds: float,
    concurrency_per_replica: float,
    target_utilization: float = 0.70,
) -> int:
    if peak_rps <= 0 or p95_service_seconds <= 0 or concurrency_per_replica <= 0:
        raise ValueError("traffic, latency and concurrency inputs must be positive")
    if not 0 < target_utilization <= 1:
        raise ValueError("target_utilization must be in (0, 1]")
    concurrent_demand = peak_rps * p95_service_seconds
    safe_capacity = concurrency_per_replica * target_utilization
    return max(2, math.ceil(concurrent_demand / safe_capacity))


def main() -> None:
    parser = argparse.ArgumentParser(description="I10 initial serving capacity calculator")
    parser.add_argument("--peak-rps", type=float, required=True)
    parser.add_argument("--p95-ms", type=float, required=True)
    parser.add_argument("--concurrency", type=float, required=True)
    parser.add_argument("--utilization", type=float, default=0.70)
    args = parser.parse_args()
    replicas = required_replicas(
        args.peak_rps,
        args.p95_ms / 1000.0,
        args.concurrency,
        args.utilization,
    )
    print(f"required_replicas={replicas}")
    print("status=CAPACITY_ESTIMATE_NOT_BENCHMARK_EVIDENCE")


if __name__ == "__main__":
    main()
