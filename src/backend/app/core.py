"""Core domain logic: signature matching and priority calculation.

These are deliberately PURE functions (no DB, no I/O) so they are trivial to unit-test
and reason about. This is where the correctness of the platform really lives.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureView:
    """Minimal, storage-agnostic view of a signature for matching."""

    id: int
    priority: int
    match_fields: dict  # {"field": expected_value, ...}


def _as_number(value: str):
    """Parse a numeric string to int/float, or return None if it isn't numeric."""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def _values_equal(expected, actual) -> bool:
    """Type-aware equality for a single field.

    We deliberately avoid the naive ``str(a) == str(b)`` compare, which silently
    conflates distinct types (``True``/``"True"``, ``None``/``"None"``, a dict and its
    repr). Rules:
      - bool only ever equals a bool of the same value — never a string or number.
      - None only ever equals None.
      - otherwise use native ``==`` (covers str, int, float, and *semantic* equality
        for nested dicts/lists), with one deliberate tolerance: a JSON-stored numeric
        string matches a number ("443" vs 443) in either direction.
    """
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    if expected is None or actual is None:
        return expected is actual
    if expected == actual:
        return True
    if isinstance(expected, (int, float)) and isinstance(actual, str):
        return _as_number(actual) == expected
    if isinstance(actual, (int, float)) and isinstance(expected, str):
        return _as_number(expected) == actual
    return False


def signature_matches(sig: SignatureView, payload: dict) -> bool:
    """A signature matches when EVERY field/value pair it defines is present in the
    payload with an equal value (a subset match).

    Edge cases:
      - A signature with no match_fields is treated as NON-matching. An empty rule
        would otherwise match every incident, which is almost certainly a config error.
      - Values are compared type-aware (see ``_values_equal``): a numeric string and a
        number compare equal ("443" vs 443), but booleans/None/nested values are NOT
        coerced into surprising string matches.
    """
    if not sig.match_fields:
        return False
    for field, expected in sig.match_fields.items():
        if field not in payload:
            return False
        if not _values_equal(expected, payload[field]):
            return False
    return True


def select_best_signature(
    signatures: list[SignatureView], payload: dict
) -> SignatureView | None:
    """Return the single best-matching signature for an incident, or None.

    Resolution policy when MULTIPLE signatures match (documented in README):
      1. Highest signature priority wins (more severe).
      2. Tie-break by specificity: more field/value pairs => more precise match.
      3. Final tie-break by id for deterministic, stable behaviour.

    With no matches this returns None (caller stores the incident as unmatched).
    """
    matches = [s for s in signatures if signature_matches(s, payload)]
    if not matches:
        return None
    return max(
        matches,
        key=lambda s: (s.priority, len(s.match_fields), s.id),
    )


def compute_priority(customer_importance: int, signature_priority: int) -> int:
    """Detection priority = customer importance * signature priority.

    Both inputs are on a 1..5 scale, giving a final score in 1..25. Multiplication is
    monotonic in both inputs (raising either never lowers priority) and keeps a very
    important customer with a severe signature strictly on top. Higher = more urgent.
    """
    return customer_importance * signature_priority
