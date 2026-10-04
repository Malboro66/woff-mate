"""Canonical #177 source/bundle entry; fixture-backed, no P1 authorization."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from scripts.ui_adoption_support import check_bindings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="execute candidate keyboard/accessibility probe")
    parser.add_argument("--evidence", type=Path, help="write smoke JSON to this explicit output")
    args = parser.parse_args()
    if args.evidence and not args.smoke:
        parser.error("--evidence requires --smoke")
    check_bindings()
    if args.smoke:
        from scripts.ui_adoption_probe import probe
        result = probe()
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0
    from woff.p0_desktop.__main__ import main as p0_main
    sys.argv = [sys.argv[0]]
    return p0_main()


if __name__ == "__main__":
    raise SystemExit(main())
