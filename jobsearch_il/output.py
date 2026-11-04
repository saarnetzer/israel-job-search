"""Render results as a terminal table, JSON or CSV."""

from __future__ import annotations

import csv
import io
import json
import shutil

from .models import Job

CSV_FIELDS = ["title", "company", "location", "source", "posted_at", "salary", "job_type", "url"]


def to_json(jobs: list[Job]) -> str:
    return json.dumps([j.to_dict() for j in jobs], ensure_ascii=False, indent=2)


def to_csv(jobs: list[Job]) -> str:
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens Hebrew correctly
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    for j in jobs:
        w.writerow(j.to_dict())
    return buf.getvalue()


def _cut(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def to_table(jobs: list[Job]) -> str:
    if not jobs:
        return "לא נמצאו משרות מתאימות. (No matching jobs.)"
    width = shutil.get_terminal_size((120, 20)).columns
    lines = []
    for i, j in enumerate(jobs, 1):
        date = j.posted_at.strftime("%d/%m/%Y") if j.posted_at else "-"
        head = f"{i:>3}. {_cut(j.title, 70)}"
        meta = " | ".join(x for x in (j.company, j.location, j.job_type, j.salary, date, j.source) if x)
        lines += [head, f"     {_cut(meta, width - 6)}", f"     {j.url}"]
        if j.extra.get("also_on"):
            lines.append("     גם ב: " + ", ".join(x["source"] for x in j.extra["also_on"]))
    return "\n".join(lines)


def render(jobs: list[Job], fmt: str) -> str:
    return {"json": to_json, "csv": to_csv}.get(fmt, to_table)(jobs)
