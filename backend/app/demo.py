"""Run the local demonstration using the configured API key without printing it."""

import json
import urllib.request

from backend.app.config import get_settings


def main() -> None:
    """Reconcile seeded inputs through the real HTTP workflow."""
    request = urllib.request.Request(
        "http://localhost:8000/runs/reconcile",
        data=b"",
        headers={"X-API-Key": get_settings().api_key.get_secret_value()},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3600) as response:
        print(json.dumps(json.load(response), indent=2))
    print("Synthetic data only. The default stub makes no model API calls.")


if __name__ == "__main__":
    main()
