"""Regression tests for the SchemaCaps re-binding rule (classify2.analyse).

Each test states a schema change and the decision Definition 1 requires:
  ASK    -> the rule must not re-bind silently (amp_strict or undecided);
  REBIND -> the change admits no new value on any authority coordinate, so a silent re-bind is sound.
Run:  python3 -m pytest -q tests/   (or: python3 tests/test_classifier.py)
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from classify2 import analyse, LEXICAL, LABEL_FREE, manifest_labeller


def T(schema):
    return {"name": "t", "inputSchema": schema}


def obj(props, closed=True, required=()):
    s = {"type": "object", "properties": props}
    if closed:
        s["additionalProperties"] = False
    if required:
        s["required"] = list(required)
    return s


def asks(old, new, lab=LEXICAL):
    a = analyse(T(old), T(new), lab)
    return bool(a["amp_strict"] or a["undecided"]), a["reasons"]


S = {"type": "string"}


# ---------- openings of a closed object (the review's counter-example) ----------
def test_closed_root_becomes_empty_schema():
    ask, why = asks(obj({"text": S}), {})
    assert ask and any(r.startswith("object_opened:<root>") for r in why), why


def test_closed_root_becomes_true():
    ask, why = asks(obj({"text": S}), True)
    assert ask and any(r.startswith("object_opened") for r in why), why


def test_closed_nested_object_becomes_empty_schema():
    old = obj({"opts": obj({"text": S})})
    new = obj({"opts": {}})
    ask, why = asks(old, new)
    assert ask and "object_opened:opts" in why, why


def test_closed_array_items_become_unconstrained():
    old = obj({"files": {"type": "array", "items": obj({"name": S})}})
    new = obj({"files": {"type": "array"}})
    ask, why = asks(old, new)
    assert ask and "object_opened:files[]" in why, why


def test_closed_object_opened_by_additional_properties():
    ask, why = asks(obj({"text": S}), obj({"text": S}, closed=False))
    assert ask and "object_opened:<root>" in why, why


def test_typed_additional_properties_widened():
    old = {"type": "object", "properties": {"text": S}, "additionalProperties": {"type": "integer"}}
    new = {"type": "object", "properties": {"text": S}, "additionalProperties": {"type": ["integer", "string"]}}
    ask, why = asks(old, new)
    assert ask and "object_opened:<root>" in why, why


def test_nested_object_changes_shape():
    old = obj({"opts": obj({"text": S})})
    new = obj({"opts": S})
    ask, why = asks(old, new)
    assert ask and "shape_changed:opts" in why, why


# ---------- narrowing changes must NOT ask ----------
def test_field_removed_from_closed_object_is_a_restriction():
    old = obj({"text": S, "opts": obj({"x": S})})
    new = obj({"text": S})
    ask, why = asks(old, new)
    assert not ask, why


def test_declaring_a_field_on_an_open_object_narrows():
    old = obj({"text": S}, closed=False)
    new = obj({"text": S, "path": S}, closed=False)
    ask, why = asks(old, new)
    assert not ask, why


def test_description_only_change_is_not_a_schema_change():
    a = analyse({"name": "t", "description": "a", "inputSchema": obj({"path": S})},
                {"name": "t", "description": "b", "inputSchema": obj({"path": S})})
    assert not a["schema_changed"] and not a["amp_strict"]


# ---------- authority coordinates ----------
def test_new_authority_argument_on_closed_object():
    ask, why = asks(obj({"command": S}), obj({"command": S, "shell": S}))
    assert ask and "new_authority_arg:shell" in why, why


def test_enum_widened_on_authority_argument():
    old = obj({"path": {"type": "string", "enum": ["/tmp"]}})
    new = obj({"path": {"type": "string", "enum": ["/tmp", "/etc"]}})
    ask, why = asks(old, new)
    assert ask and "widened:path" in why, why


def test_null_is_not_absence():
    old = obj({"regionUrl": S})
    new = obj({"regionUrl": {"type": ["string", "null"]}})
    ask, why = asks(old, new)
    assert ask and "nullable:regionUrl" in why, why


def test_required_authority_argument_becomes_optional():
    old = obj({"path": S}, required=["path"])
    new = obj({"path": S})
    ask, why = asks(old, new)
    assert ask and "became_optional:path" in why, why


def test_default_changed_on_authority_argument():
    old = obj({"path": {"type": "string", "default": "/tmp"}})
    new = obj({"path": {"type": "string", "default": "/"}})
    ask, why = asks(old, new)
    assert ask and "default_changed:path" in why, why


def test_combinator_in_old_schema_on_authority_path_is_undecided():
    old = obj({"path": S, "mode": S})
    old["anyOf"] = [{"required": ["path"]}, {"required": ["mode"]}]
    new = obj({"path": S, "mode": {"type": "string", "enum": ["a"]}})
    ask, why = asks(old, new)
    assert ask and any(r.startswith("cross_constraint:") for r in why), why


def test_unresolved_ref_is_undecided():
    new = obj({"path": {"$ref": "#/$defs/missing"}})
    ask, why = asks(obj({"path": S}), new)
    assert ask and "unresolved_ref" in why, why


# ---------- incompatible changes (policy: the rule is orthogonal to compatibility) ----------
def test_incompatible_but_narrowing_rebinds():
    # a field becomes required: old calls without it break (incompatible), no new value is admitted
    a = analyse(T(obj({"path": S, "text": S})), T(obj({"path": S, "text": S}, required=["text"])), LEXICAL)
    assert a["compatible"] is False and not (a["amp_strict"] or a["undecided"]), a["reasons"]


def test_incompatible_and_amplifying_asks():
    # rename path -> file_path on a closed object: incompatible AND a new authority argument
    ask, why = asks(obj({"path": S}), obj({"file_path": S}))
    assert ask and "new_authority_arg:file_path" in why, why


# ---------- labellers ----------
def test_non_lexical_widening_is_missed_by_lexical_but_caught_label_free():
    old = obj({"saveScript": {"type": "boolean", "enum": [False]}})
    new = obj({"saveScript": {"type": "boolean"}})
    assert not asks(old, new, LEXICAL)[0]          # the lexical labeller misses it (recall < 1)
    assert asks(old, new, LABEL_FREE)[0]           # label-free mode catches it


def test_manifest_unknown_path_is_authority():
    lab = manifest_labeller(authority=["path"], inert=["limit"])
    assert asks(obj({"path": S}), obj({"path": S, "saveScript": S}), lab)[0]      # unknown => authority
    assert not asks(obj({"path": S}), obj({"path": S, "limit": S}), lab)[0]      # declared inert


if __name__ == "__main__":
    fails = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_") and callable(f):
            try:
                f(); print("PASS", k)
            except AssertionError as e:
                fails += 1; print("FAIL", k, e)
    sys.exit(1 if fails else 0)
