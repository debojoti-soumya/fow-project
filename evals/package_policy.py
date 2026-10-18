#!/usr/bin/env python3
"""Publish stored runs and Elo to the lab site."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_runs import publish  # noqa: E402

SITE = "https://fow-lab.debojotisoumya.workers.dev"


def main() -> None:
    publish()
    print(SITE)


if __name__ == "__main__":
    main()
