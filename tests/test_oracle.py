"""The oracle must detect planted violations and stay silent on sound changes (tests the tester)."""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import oracle2

S = {"type": "string"}


def o(p, closed=True, req=()):
    s = {"type": "object", "properties": p}
    if closed:
        s["additionalProperties"] = False
    if req:
        s["required"] = list(req)
    return s


def kinds(fn, so, sn):
    return {i[0] for i in fn(so, sn)[0]}


def test_label_free_detects_widening_optional_and_default():
    assert "admitted_now_refused_before" in kinds(oracle2.audit_label_free, o({"x": {"enum": ["a"]}}), o({"x": {"enum": ["a", "b"]}}))
    assert "admitted_now_refused_before" in kinds(oracle2.audit_label_free, o({"x": S}, req=["x"]), o({"x": S}))
    assert "default_changed" in kinds(oracle2.audit_label_free, o({"x": {"type": "string", "default": "a"}}),
                                      o({"x": {"type": "string", "default": "b"}}))


def test_label_free_clean_on_narrowing():
    assert not kinds(oracle2.audit_label_free, o({"x": {"enum": ["a", "b"]}}), o({"x": {"enum": ["a"]}}))


def test_lexical_detects_opening_new_arg_and_widening():
    assert "opened" in kinds(oracle2.audit_lexical, o({"text": S}), {"type": "object"})
    assert "new_authority_arg" in kinds(oracle2.audit_lexical, o({"text": S}), o({"text": S, "path": S}))
    assert "widened" in kinds(oracle2.audit_lexical, o({"path": {"enum": ["/tmp"]}}), o({"path": {"enum": ["/tmp", "/etc"]}}))


def test_lexical_ignores_non_authority_widening():
    assert not kinds(oracle2.audit_lexical, o({"text": {"enum": ["a"]}}), o({"text": {"enum": ["a", "b"]}}))


def test_label_free_detects_removed_defaulted_declaration():
    # Deviation 11: removing a defaulted declaration from a closed object turns its effective value into ⊥.
    assert "removed_to_bottom" in kinds(oracle2.audit_label_free, o({"x": {"type": "string", "default": "a"}, "y": S}),
                                        o({"y": S}))
