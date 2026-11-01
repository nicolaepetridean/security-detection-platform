"""Unit tests for the pure matching & priority logic (no DB)."""
from app.core import (
    SignatureView,
    compute_priority,
    select_best_signature,
    signature_matches,
)

BROAD = SignatureView(id=1, priority=3, match_fields={"event_type": "auth_fail"})
SSH = SignatureView(
    id=2, priority=4, match_fields={"event_type": "auth_fail", "service": "ssh"}
)
C2 = SignatureView(
    id=3, priority=5, match_fields={"event_type": "c2", "protocol": "https"}
)


def test_exact_match():
    assert signature_matches(BROAD, {"event_type": "auth_fail"})


def test_subset_match_ignores_extra_fields():
    assert signature_matches(BROAD, {"event_type": "auth_fail", "ip": "1.2.3.4"})


def test_missing_field_no_match():
    assert not signature_matches(SSH, {"event_type": "auth_fail"})


def test_wrong_value_no_match():
    assert not signature_matches(BROAD, {"event_type": "scan"})


def test_value_type_coercion():
    sig = SignatureView(id=9, priority=1, match_fields={"port": 443})
    assert signature_matches(sig, {"port": "443"})


def test_numeric_string_coercion_both_directions():
    # Number stored, numeric string sent -- and the reverse -- both match.
    assert signature_matches(
        SignatureView(id=16, priority=1, match_fields={"port": 443}), {"port": "443"}
    )
    assert signature_matches(
        SignatureView(id=17, priority=1, match_fields={"port": "443"}), {"port": 443}
    )


def test_bool_not_coerced_to_string_or_number():
    # A string "True" must NOT match a JSON boolean true (old str()-compare bug).
    str_sig = SignatureView(id=11, priority=1, match_fields={"enabled": "True"})
    assert not signature_matches(str_sig, {"enabled": True})
    # A boolean rule matches only a real boolean, never "1" or 1.
    bool_sig = SignatureView(id=12, priority=1, match_fields={"enabled": True})
    assert signature_matches(bool_sig, {"enabled": True})
    assert not signature_matches(bool_sig, {"enabled": "1"})
    assert not signature_matches(bool_sig, {"enabled": 1})


def test_none_matches_only_none():
    sig = SignatureView(id=13, priority=1, match_fields={"user": None})
    assert signature_matches(sig, {"user": None})
    assert not signature_matches(sig, {"user": "None"})


def test_nested_object_semantic_equality():
    sig = SignatureView(id=14, priority=1, match_fields={"meta": {"k": "v"}})
    assert signature_matches(sig, {"meta": {"k": "v"}})
    assert not signature_matches(sig, {"meta": {"k": "other"}})


def test_list_value_order_sensitive():
    sig = SignatureView(id=15, priority=1, match_fields={"ports": [1, 2]})
    assert signature_matches(sig, {"ports": [1, 2]})
    assert not signature_matches(sig, {"ports": [2, 1]})


def test_empty_match_fields_never_matches():
    empty = SignatureView(id=10, priority=5, match_fields={})
    assert not signature_matches(empty, {"anything": "x"})


def test_no_match_returns_none():
    assert select_best_signature([BROAD, SSH, C2], {"event_type": "scan"}) is None


def test_multiple_matches_picks_highest_priority():
    # Both BROAD (p3) and SSH (p4) match; SSH wins on priority.
    best = select_best_signature([BROAD, SSH], {"event_type": "auth_fail", "service": "ssh"})
    assert best.id == SSH.id


def test_tie_break_by_specificity():
    # Two signatures, same priority; the more specific (more fields) wins.
    a = SignatureView(id=1, priority=3, match_fields={"event_type": "auth_fail"})
    b = SignatureView(
        id=2, priority=3, match_fields={"event_type": "auth_fail", "service": "ssh"}
    )
    best = select_best_signature([a, b], {"event_type": "auth_fail", "service": "ssh"})
    assert best.id == b.id


def test_priority_is_product():
    assert compute_priority(5, 4) == 20
    assert compute_priority(1, 1) == 1
    assert compute_priority(3, 5) == 15
