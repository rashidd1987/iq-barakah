#!/usr/bin/env python3
"""Record a GitHub-side deployment decision in the shared approval center."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--status", choices=("approved", "rejected"), required=True)
    args = parser.parse_args()
    api_url = os.environ.get("APPROVAL_API_URL", "").rstrip("/")
    secret = os.environ.get("APPROVAL_API_SECRET", "")
    if not api_url or not secret:
        print("Approval API configuration is missing.", file=sys.stderr)
        return 2
    request = Request(
        f"{api_url}/approvals/{args.approval_id}/decision",
        data=json.dumps({"status": args.status}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "mizan-github-approval-gate/2",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
        print(f"Shared approval status: {payload['status']}")
        return 0
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        print(f"Could not synchronize approval: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
