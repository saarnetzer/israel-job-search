"""Load config.yaml (sources settings, company lists, saved searches)."""

from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from typing import Any

import yaml

from .models import SearchCriteria

DEFAULT_PATHS = [Path("config.yaml"), Path.home() / ".config" / "jobsearch-il" / "config.yaml"]


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    candidates = [Path(path)] if path else DEFAULT_PATHS
    for p in candidates:
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    if path:
        raise FileNotFoundError(path)
    return {}


def criteria_from_dict(d: dict[str, Any]) -> SearchCriteria:
    names = {f.name for f in fields(SearchCriteria)}
    unknown = set(d) - names
    if unknown:
        raise ValueError(f"Unknown search fields: {', '.join(sorted(unknown))}")
    data = dict(d)
    for k in ("keywords", "exclude_keywords", "locations", "job_types", "companies", "exclude_companies", "sources"):
        if isinstance(data.get(k), str):
            data[k] = [data[k]]
    return SearchCriteria(**data)
