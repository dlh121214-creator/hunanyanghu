from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import create_app


def main() -> None:
    output = PROJECT_ROOT / "docs" / "openapi.json"
    output.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
