#!/usr/bin/env python3
"""Request a one-time Telegram approval and wait for the owner's decision."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def api_request(
    url: str,
    secret: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "mizan-github-approval-gate/1",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def api_request_with_retry(
    url: str,
    secret: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    attempts: int = 6,
) -> dict[str, object]:
    for attempt in range(1, attempts + 1):
        try:
            return api_request(url, secret, method=method, payload=payload)
        except HTTPError as exc:
            if exc.code < 500 or attempt == attempts:
                raise
        except (URLError, TimeoutError):
            if attempt == attempts:
                raise
        time.sleep(min(5 * attempt, 20))
    raise RuntimeError("unreachable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--risk", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--ttl-minutes", type=int, default=60)
    parser.add_argument("--poll-seconds", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_url = os.environ.get("APPROVAL_API_URL", "").rstrip("/")
    secret = os.environ.get("APPROVAL_API_SECRET", "")
    if not api_url or not secret:
        print("Approval API configuration is missing.", file=sys.stderr)
        return 2

    try:
        approval = api_request_with_retry(
            f"{api_url}/approvals",
            secret,
            method="POST",
            payload={
                "idempotency_key": args.idempotency_key,
                "project": args.project,
                "action": args.action,
                "description": args.description,
                "risk": args.risk,
                "ttl_minutes": args.ttl_minutes,
            },
        )
        approval_id = str(approval["id"])
        print(f"Telegram approval requested: {approval_id}")

        while True:
            status_payload = api_request_with_retry(
                f"{api_url}/approvals/{approval_id}",
                secret,
            )
            status = status_payload.get("status")
            if status == "approved":
                print("Production action approved.")
                return 0
            if status in {"rejected", "expired"}:
                print(f"Production action stopped: {status}.", file=sys.stderr)
                return 1
            if status != "pending":
                print("Approval API returned an invalid status.", file=sys.stderr)
                return 2
            time.sleep(max(5, args.poll_seconds))
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"Approval API is unavailable: {type(exc).__name__}.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
