"""Workflows module — unit tests (Task 1 of the workflows plan)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.workflows as WF  # noqa: E402


def test_templates_well_formed():
    assert WF.TEMPLATES, "no templates defined"
    for t in WF.TEMPLATES:
        assert t.get("id"), f"template missing id: {t}"
        assert t.get("when"), f"template {t['id']} missing when"
        assert t.get("actions"), f"template {t['id']} missing actions"
        # every action must be a known Applivery action
        for a in t["actions"]:
            assert a["action"] in WF.APPLIVERY_ACTIONS, \
                f"template {t['id']} unknown action {a['action']}"


def test_action_catalog_complete():
    expected = {"lock", "wipe", "message", "locate", "reboot",
                 "clear_passcode", "notify", "custom"}
    assert set(WF.APPLIVERY_ACTIONS) == expected


def test_build_from_template_route_exit():
    pol = WF.build_policy_from_template("wf-block-on-route-exit")
    assert pol["id"] == "pol-wf-block-on-route-exit"
    assert pol["source"] == "template"
    # when must flag off_route
    fields = [c["field"] for c in pol["when"]]
    assert "signal:route_state.route_state" in fields
    # actions must be valid
    for a in pol["actions"]:
        assert a["action"] in WF.APPLIVERY_ACTIONS


def test_build_from_template_with_device_ids():
    pol = WF.build_policy_from_template(
        "wf-ciso-deviation-500", device_ids=["dev-002"])
    dev_cond = [c for c in pol["when"] if c["field"] == "device_id"]
    assert dev_cond, "device_ids condition not added"
    assert dev_cond[0]["value"] == ["dev-002"]


def test_build_from_template_unknown():
    try:
        WF.build_policy_from_template("nope")
        assert False, "should have raised"
    except ValueError:
        pass


def test_build_custom_basic():
    pol = WF.build_custom_policy({
        "name": "Mi workflow",
        "trigger": "route_exit",
        "action": "lock",
        "severity": "high",
    })
    assert pol["source"] == "custom"
    assert pol["name"] == "Mi workflow"
    assert pol["severity"] == "high"
    fields = [c["field"] for c in pol["when"]]
    assert "signal:route_state.route_state" in fields
    assert pol["actions"] == [{"action": "lock", "params": {}}]


def test_build_custom_with_deviation_threshold():
    pol = WF.build_custom_policy({
        "name": "W",
        "trigger": "route_exit",
        "min_deviation_m": 500,
        "action": "message",
        "action_text": "Vuelve a la ruta",
    })
    dev_c = [c for c in pol["when"] if c["field"].endswith("route_deviation_m")]
    assert dev_c, "deviation threshold condition missing"
    assert dev_c[0]["op"] == "gt" and dev_c[0]["value"] == 500
    assert pol["actions"][0]["action"] == "message"
    assert pol["actions"][0]["params"]["text"] == "Vuelve a la ruta"


def test_build_custom_validation():
    # missing name
    try:
        WF.build_custom_policy({"trigger": "rooted", "action": "wipe"})
        assert False, "should require name"
    except ValueError:
        pass
    # bad trigger
    try:
        WF.build_custom_policy({"name": "x", "trigger": "bogus", "action": "lock"})
        assert False, "should reject bad trigger"
    except ValueError:
        pass
    # bad action
    try:
        WF.build_custom_policy({"name": "x", "trigger": "rooted", "action": "bogus"})
        assert False, "should reject bad action"
    except ValueError:
        pass
    # invalid min_deviation_m must raise (not silently dropped) — reviewer MINOR#2
    try:
        WF.build_custom_policy({
            "name": "x", "trigger": "route_exit",
            "min_deviation_m": "not-a-number", "action": "lock"})
        assert False, "should reject non-int min_deviation_m"
    except ValueError:
        pass


def test_trigger_and_action_options_for_ui():
    trigs = WF.trigger_options()
    acts = WF.action_options()
    assert len(trigs) == 6
    assert all("value" in t and "label" in t for t in trigs)
    assert len(acts) == len(WF.APPLIVERY_ACTIONS)
    assert all("value" in a and "label" in a for a in acts)
