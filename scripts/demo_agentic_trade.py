"""Demo script: submit a trade to the Agent Controller and display results.

Usage (inside Docker tools container):
    python scripts/demo_agentic_trade.py

Usage (from host, if agent-controller is exposed on localhost:8015):
    AGENT_URL=http://localhost:8015 python scripts/demo_agentic_trade.py
"""

import os
import sys
import httpx


def main():
    base_url = os.getenv("AGENT_URL", "http://agent-controller:8015")
    payload = {
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 100,
        "reason": "Momentum signal detected, risk within limits, agent demo trade.",
    }

    print("=== Agent Controller Demo ===")
    print(f"URL: {base_url}/agent/trade")
    print(f"Payload: {payload}")
    print()

    try:
        resp = httpx.post(f"{base_url}/agent/trade", json=payload, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    print(f"workflow_id      : {data['workflow_id']}")
    print(f"correlation_id   : {data['correlation_id']}")
    print(f"decision         : {data['decision']}")
    print(f"confidence_score : {data['confidence_score']}")
    print(f"status           : {data['status']}")

    if data.get("order_id"):
        print(f"order_id         : {data['order_id']}")
        print(f"fill_price       : {data['fill_price']}")
        print()
        print(">>> Order FILLED successfully!")
    elif data["decision"] == "NEEDS_HUMAN":
        print()
        print(">>> Confidence below threshold – human review required.")
    elif data["decision"] == "DENY":
        print()
        print(">>> Trade DENIED by agent (risk violations).")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
