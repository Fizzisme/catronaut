"""Manual end-to-end check against a running service and a real model.

Kept out of the pytest suite on purpose: real generation on qwen3:4b takes
minutes on CPU.

    python scripts/smoke_test.py [base_url]
"""

import sys

import httpx

# The model emits emoji; the Windows console defaults to cp1252 and would raise.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
PROMPT = (
    "My login form uses a 10px gray placeholder as its only label, and the "
    "submit button is light gray on white. Give me 2 concrete fixes."
)


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=600.0) as client:
        health = client.get("/health").json()
        print(f"health: {health}")
        if health["model_backend"] != "up":
            print("model backend is down — is `ollama serve` running?")
            return 1

        print(f"\ncalling {health['model']} (this can take minutes on CPU)...")
        response = client.post("/ui-ux/analyze", json={"prompt": PROMPT})
        response.raise_for_status()
        body = response.json()

    print(f"\n--- result ({body['model']}) ---\n{body['result']}")

    if "</think>" in body["result"]:
        print("\nFAIL: reasoning leaked into the response")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
