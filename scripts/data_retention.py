"""Retain previously verified non-price sections when an upstream data API is unavailable.

Never fabricate missing financial observations. Existing data are explicitly labeled
with their original retrieval timestamp; latest market OHLCV stays fresh/independent.
"""

from __future__ import annotations

from copy import deepcopy


def _has_data(section: str, value: object) -> bool:
    if not isinstance(value, dict):
        return False
    key = {
        "institutional": "total_net",
        "margin": "margin_balance",
        "valuation": "PER",
        "fundamentals": "quarters",
        "news": "articles",
    }[section]
    return bool(value.get(key))


_OVERVIEW_KEYS = {
    "institutional": ("foreign_net_today", "trust_net_today", "dealer_net_today"),
    "valuation": ("per", "pbr"),
    "news": ("news_positive", "news_negative", "news_neutral"),
}


def retain_optional_sections(
    current: dict, previous: dict | None, *, provider_unavailable: bool
) -> dict:
    """Return JSON with old optional data only where the current fetch is unavailable.

    Price, volume, predictions, technical indicators and the observation date
    always come from the *new* computation, never from the old snapshot.
    """
    result = deepcopy(current)
    result["retained_section_dates"] = {}
    if not provider_unavailable or not isinstance(previous, dict):
        return result

    previous_overview = previous.get("overview") or {}
    new_overview = result.get("overview") or {}
    prior_dates = previous.get("retained_section_dates") or {}

    for section in ("institutional", "margin", "valuation", "fundamentals", "news"):
        if _has_data(section, result.get(section)):
            continue
        old_value = previous.get(section)
        if not _has_data(section, old_value):
            continue
        result[section] = deepcopy(old_value)
        # A section can be retained across multiple runs. Never reset its provenance.
        source_date = prior_dates.get(section) or previous.get("updated_at")
        if source_date:
            result["retained_section_dates"][section] = str(source_date)
        for key in _OVERVIEW_KEYS.get(section, ()):
            if previous_overview.get(key) is not None:
                new_overview[key] = previous_overview[key]

    if result["retained_section_dates"]:
        result["overview"] = new_overview
    return result
