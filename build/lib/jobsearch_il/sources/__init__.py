"""Registry of all job sources.

To add a site: subclass `Source`, implement `search()`, and add it to SOURCES.
"""

from __future__ import annotations

from .alljobs import AllJobsSource
from .ats import CareerPagesSource, ComeetSource, GreenhouseSource, LeverSource
from .base import Source
from .drushim import DrushimSource
from .jobmaster import JobMasterSource
from .linkedin import LinkedInSource

SOURCES: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (
        DrushimSource,
        AllJobsSource,
        JobMasterSource,
        LinkedInSource,
        ComeetSource,
        GreenhouseSource,
        LeverSource,
        CareerPagesSource,
    )
}

__all__ = ["SOURCES", "Source"]
