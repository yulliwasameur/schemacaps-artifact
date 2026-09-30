"""Soundness probes for the inclusion checker.

`raw` is jsonsubschema as published; `guarded` is classify2.sub (boolean normalisation + counterexample guard).
A verdict is UNSOUND when it claims a ⊆ b although a value valid under a and invalid under b exists.
The test documents the raw checker's known defect and requires the guarded checker to have none on these probes.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from classify import sub as raw
from classify2 import sub as guarded, counterexample, _NOCEX

PROBES = [
    ("bool vs bool/enum[F]", {"type": "boolean"}, {"type": "boolean", "enum": [False]}),
    ("bool vs const F", {"type": "boolean"}, {"const": False}),
    ("bool vs enum[F]", {"type": "boolean"}, {"enum": [False]}),
    ("[bool,null] vs bool/enum[F]", {"type": ["boolean", "null"]}, {"type": "boolean", "enum": [False]}),
    ("nested bool widened", {"type": "object", "properties": {"x": {"type": "boolean"}}},
     {"type": "object", "properties": {"x": {"const": False}}}),
    ("enum[T,F] vs enum[F]", {"enum": [True, False]}, {"enum": [False]}),
    ("int vs int/enum[1]", {"type": "integer"}, {"type": "integer", "enum": [1]}),
    ("str vs str/const a", {"type": "string"}, {"type": "string", "const": "a"}),
    ("str vs str/pattern", {"type": "string"}, {"type": "string", "pattern": "^a"}),
    ("str vs str/maxLength", {"type": "string"}, {"type": "string", "maxLength": 3}),
    ("num vs int", {"type": "number"}, {"type": "integer"}),
    ("[str,null] vs str", {"type": ["string", "null"]}, {"type": "string"}),
    ("arr vs arr/unique", {"type": "array", "items": {"type": "integer"}},
     {"type": "array", "items": {"type": "integer"}, "uniqueItems": True}),
    ("open vs closed", {"type": "object"}, {"type": "object", "additionalProperties": False}),
    ("enum[a,b] vs enum[a]", {"enum": ["a", "b"]}, {"enum": ["a"]}),
    ("anyOf vs str", {"anyOf": [{"type": "string"}, {"type": "integer"}]}, {"type": "string"}),
    ("{} vs str", {}, {"type": "string"}),
]

KNOWN_RAW_DEFECTS = {"bool vs bool/enum[F]", "bool vs const F", "bool vs enum[F]"}


def _has_cex(a, b):
    c = counterexample(a, b, n=300)
    return c is not _NOCEX and not (isinstance(c, str) and c == "gen_error")


def test_raw_checker_defect_is_documented():
    found = {name for name, a, b in PROBES if raw(a, b) is True and _has_cex(a, b)}
    assert KNOWN_RAW_DEFECTS <= found, found


def test_guarded_checker_has_no_unsound_verdict():
    bad = [name for name, a, b in PROBES if guarded(a, b) is True and _has_cex(a, b)]
    assert not bad, bad


def test_guarded_checker_keeps_true_inclusions():
    assert guarded({"type": "boolean", "enum": [False]}, {"type": "boolean"}) is True
    assert guarded({"type": "string", "enum": ["a"]}, {"type": "string"}) is True
    assert guarded({"type": "integer"}, {"type": "number"}) is True


if __name__ == "__main__":
    for f in (test_raw_checker_defect_is_documented, test_guarded_checker_has_no_unsound_verdict,
              test_guarded_checker_keeps_true_inclusions):
        f(); print("PASS", f.__name__)
