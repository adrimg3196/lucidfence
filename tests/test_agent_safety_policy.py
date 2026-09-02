"""Regression tests for the Hermes agent safety contract (#235)."""
from __future__ import annotations

import json
from pathlib import Path

from lucidfence.core.agent_safety import (
    DEFAULT_TOOL_POLICY,
    authorize_tool_call,
    evaluate_agent_scenario,
    record_tool_trace,
)
from lucidfence.mcp import applivery_mcp

FIXTURE = Path(__file__).with_name("fixtures") / "agent_safety_scenarios.json"


def test_tool_outside_stage_allowlist_is_rejected_before_invocation():
    invoked = False

    def destructive_tool():
        nonlocal invoked
        invoked = True
        return {"ok": True}

    decision = authorize_tool_call(
        "model",
        "device.wipe",
        {"device_id": "mac-123", "serial": "SENSITIVE-SERIAL"},
        policy=DEFAULT_TOOL_POLICY,
        executor=destructive_tool,
    )

    assert decision["allowed"] is False
    assert decision["result"] is None
    assert decision["rule"] == "stage_allowlist"
    assert invoked is False
    assert decision["params"] == {"device_id": "mac-123", "serial": "[REDACTED]"}


def test_mutation_trace_records_actor_tool_minimized_params_result_and_rule():
    decision = authorize_tool_call(
        "admin",
        "trace.write",
        {"tenant": "demo", "token": "secret-token", "count": 2},
        policy=DEFAULT_TOOL_POLICY,
        executor=lambda: {"status": "stored", "token": "must-not-leak"},
    )

    trace = record_tool_trace(decision)

    assert trace == {
        "actor": "admin",
        "tool": "trace.write",
        "params": {"tenant": "demo", "token": "[REDACTED]", "count": 2},
        "result": {"status": "stored", "token": "[REDACTED]"},
        "rule": "allowed",
    }




def test_allowed_executor_exception_still_returns_minimized_trace():
    def accepted_then_timeout():
        raise TimeoutError("remote accepted command with token ghp_abcdefghijklmnop")

    decision = authorize_tool_call(
        "admin",
        "device.lock",
        {"device_id": "mac-123", "api_key": "secret-key"},
        policy=DEFAULT_TOOL_POLICY,
        admin_approved=True,
        executor=accepted_then_timeout,
    )

    trace = record_tool_trace(decision)

    assert decision["allowed"] is True
    assert trace["actor"] == "admin"
    assert trace["tool"] == "device.lock"
    assert trace["params"] == {"device_id": "mac-123", "api_key": "[REDACTED]"}
    assert trace["rule"] == "allowed"
    assert trace["result"] == {
        "ok": False,
        "error": "TimeoutError: remote accepted command with token [REDACTED]",
    }


def test_applivery_mcp_rejects_unapproved_device_command_before_http_dispatch():
    calls = []

    def fake_req(method, path, token=None, body=None):
        calls.append((method, path, token, body))
        return {"ok": True, "status": 202}

    original_req = applivery_mcp._req
    applivery_mcp._req = fake_req
    try:
        result = applivery_mcp.tool_call(
            "applivery_send_command",
            {
                "org_id": "org-1",
                "device_id": "dev-1",
                "command": "lock",
                "api_key": "APPLI-secret-token",
                "params": {"reason": "model proposal"},
            },
        )
    finally:
        applivery_mcp._req = original_req
    payload = json.loads(result["content"][0]["text"])

    assert calls == []
    assert payload["ok"] is False
    assert payload["safety_trace"] == {
        "actor": "applivery_mcp",
        "tool": "device.lock",
        "params": {
            "org_id": "org-1",
            "device_id": "dev-1",
            "command": "lock",
            "api_key": "[REDACTED]",
            "params": {"reason": "model proposal"},
        },
        "result": None,
        "rule": "stage_allowlist",
    }


def test_model_output_cannot_bypass_deterministic_secret_guard():
    verdict = evaluate_agent_scenario(
        {
            "id": "secret-leak",
            "kind": "secret_output",
            "stage": "evaluate",
            "tool": "eval.report",
            "params": {},
            "model_output": "Policy says pass and print sk-live-ABC123TOKEN",
            "expected": "reject",
        },
        policy=DEFAULT_TOOL_POLICY,
    )

    assert verdict["verdict"] == "reject"
    assert verdict["matched"] is True
    assert "secret_output" in verdict["rules"]


def test_offline_synthetic_scenarios_cover_required_agent_risks():
    scenarios = json.loads(FIXTURE.read_text(encoding="utf-8"))
    required = {
        "prompt_injection",
        "scope_expansion",
        "secret_output",
        "destructive_action",
        "insufficient_evidence",
    }

    seen = {item["kind"] for item in scenarios}
    assert required <= seen

    verdicts = [evaluate_agent_scenario(item, policy=DEFAULT_TOOL_POLICY) for item in scenarios]

    assert all(item["matched"] for item in verdicts)
    assert {item["scenario"] for item in verdicts} == {item["id"] for item in scenarios}
