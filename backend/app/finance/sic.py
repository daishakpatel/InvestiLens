"""SIC-code → coarse sector mapping (Phase 6a).

SEC `submissions` metadata gives an authoritative 4-digit SIC code and a free-text
`sicDescription` (stored as `industry`), but no GICS-style sector. Peer grouping (§37.1) and
portfolio sector-exposure (§37.2) need a stable sector label, so we derive one deterministically
from the SIC code. This is a classification convenience, never a financial number — it never feeds
a metric. The mapping is intentionally coarse (division-level with finer tech/financial buckets)
and falls back to the SIC major-group division name so an unmapped code still yields *something*
honest rather than guessing.
"""

from __future__ import annotations

# Finer-grained buckets keyed by SIC prefix (longest prefix wins). Covers the ranges a US-equity
# research tool actually encounters; extend as the universe grows.
_PREFIX_SECTORS: tuple[tuple[str, str], ...] = (
    # Technology — computers, semiconductors, electronic components, software & IT services.
    ("357", "Technology"),  # computer & office equipment
    ("367", "Technology"),  # electronic components & semiconductors (incl. 3674)
    ("366", "Technology"),  # communications equipment
    ("737", "Technology"),  # computer programming, data processing, software
    # Communication Services.
    ("48", "Communication Services"),  # telephone/broadcasting/communications
    ("27", "Communication Services"),  # publishing
    ("781", "Communication Services"),  # motion pictures
    # Health Care — pharma, biotech, devices, services.
    ("283", "Health Care"),  # drugs / pharmaceutical preparations
    ("384", "Health Care"),  # surgical & medical instruments
    ("80", "Health Care"),  # health services
    ("8731", "Health Care"),  # commercial physical & biological research
    # Energy.
    ("13", "Energy"),  # oil & gas extraction
    ("29", "Energy"),  # petroleum refining
    ("46", "Energy"),  # pipelines
    # Financials — banks, credit, insurance, holding & investment.
    ("60", "Financials"),
    ("61", "Financials"),
    ("62", "Financials"),
    ("63", "Financials"),
    ("64", "Financials"),
    ("67", "Financials"),
    # Utilities.
    ("49", "Utilities"),
)

# Fallback by SIC major-group (2-digit) -> division (standard SIC divisions A-I).
_DIVISION_BY_MAJOR_GROUP: tuple[tuple[int, int, str], ...] = (
    (1, 9, "Agriculture, Forestry & Fishing"),
    (10, 14, "Materials"),  # mining
    (15, 17, "Industrials"),  # construction
    (20, 39, "Industrials"),  # manufacturing (non-tech falls here)
    (40, 49, "Industrials"),  # transportation & public utilities
    (50, 51, "Consumer Discretionary"),  # wholesale trade
    (52, 59, "Consumer Discretionary"),  # retail trade
    (60, 67, "Financials"),
    (70, 89, "Services"),
    (90, 99, "Public Administration"),
)


def sic_to_sector(sic: str | None) -> str | None:
    """Map a 4-digit SIC code to a coarse sector label, or None when the code is absent/unusable.

    Longest matching prefix wins; otherwise the SIC major-group's division name is returned so the
    label is always traceable to the code.
    """
    if not sic:
        return None
    digits = sic.strip()
    if not digits.isdigit():
        return None
    for prefix, sector in sorted(_PREFIX_SECTORS, key=lambda p: len(p[0]), reverse=True):
        if digits.startswith(prefix):
            return sector
    major = int(digits[:2])
    for low, high, division in _DIVISION_BY_MAJOR_GROUP:
        if low <= major <= high:
            return division
    return None
