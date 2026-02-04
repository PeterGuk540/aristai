import os
import sys

import httpx


def main() -> int:
    api_base = os.getenv("API_BASE", "http://localhost:8000")
    auth_token = os.getenv("AUTH_TOKEN")

    if not auth_token:
        print("AUTH_TOKEN env var is required for this check.", file=sys.stderr)
        return 1

    url = f"{api_base.rstrip('/')}/api/voice/agent/signed-url"
    headers = {"Authorization": f"Bearer {auth_token}"}

    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code >= 400:
        print(f"Request failed ({response.status_code}): {response.text}", file=sys.stderr)
        return 1

    payload = response.json()
    signed_url = payload.get("signed_url")
    if not signed_url:
        print(f"signed_url missing in response: {payload}", file=sys.stderr)
        return 1

    print(signed_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
