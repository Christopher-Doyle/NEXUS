"""Write or verify the checked-in HTTP contract against the FastAPI app."""

import argparse
import json
from pathlib import Path

from app.main import app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed schema is stale")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        if not destination.exists() or destination.read_text(encoding="utf-8") != rendered:
            print("docs/openapi.json is stale; run python scripts/export_openapi.py")
            return 1
        print("OpenAPI schema matches the application")
        return 0
    destination.write_text(rendered, encoding="utf-8")
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
