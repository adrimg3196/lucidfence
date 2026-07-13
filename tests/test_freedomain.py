"""TDD: DigitalPlat FreeDomain whitelabel helper (offline + live-safe).

Covers:
  - core/freedomain.suggest_dns_records builds SPF/DKIM/DMARC/MX records
  - is_freedomain_suffix detects FreeDomain extensions
  - validate() returns a structured report; we patch the DoH lookup to avoid
    real network so the test is deterministic and offline.
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import freedomain  # noqa: E402


def test_suggest_builds_expected_records():
    sug = freedomain.suggest_dns_records(
        "acme-fence.dpdns.org",
        atomicmail_inbox="acme@atomicmail.ai",
        dkim_selector="atomicmail",
        dashboard_target="lucidfence.example.com",
        receive_mail=True,
    )
    types = {r["type"] for r in sug["records"]}
    assert {"TXT", "CNAME", "MX"}.issubset(types), types
    spf = [r for r in sug["records"] if r["type"] == "TXT" and r["name"] == "acme-fence.dpdns.org"]
    assert spf and "include:_spf.atomicmail.ai" in spf[0]["value"]
    dkim = [r for r in sug["records"] if r["type"] == "CNAME" and "_domainkey" in r["name"]]
    assert dkim and dkim[0]["value"].endswith("atomicmail.ai")
    dash = [r for r in sug["records"] if r["name"] == "acme-fence.dpdns.org" and r["type"] == "CNAME"]
    assert dash and dash[0]["value"] == "lucidfence.example.com"


def test_suggest_without_dashboard_and_mail():
    sug = freedomain.suggest_dns_records("x.us.kg", receive_mail=False)
    # No MX when receive_mail False, no dashboard CNAME without target.
    assert not any(r["type"] == "MX" for r in sug["records"])
    assert not any(r["type"] == "CNAME" and r["name"] == "x.us.kg" for r in sug["records"])


def test_is_freedomain_suffix():
    assert freedomain.is_freedomain_suffix("foo.dpdns.org") is True
    assert freedomain.is_freedomain_suffix("foo.us.kg") is True
    assert freedomain.is_freedomain_suffix("foo.qzz.io") is True
    assert freedomain.is_freedomain_suffix("google.com") is False


def test_validate_offline_with_mock_doh():
    fake = {
        ("acme-fence.dpdns.org", "NS"): ["ns1.digitalplat.org."],
        ("acme-fence.dpdns.org", "TXT"): ["v=spf1 include:_spf.atomicmail.ai ~all"],
        ("atomicmail._domainkey.acme-fence.dpdns.org", "CNAME"): ["atomicmail._domainkey.atomicmail.ai."],
        ("_dmarc.acme-fence.dpdns.org", "TXT"): ["v=DMARC1; p=quarantine;"],
    }

    def fake_doh(name, rtype, timeout=8.0):
        return fake.get((name, rtype), [])

    with mock.patch.object(freedomain, "_doh_query", fake_doh):
        rep = freedomain.validate("acme-fence.dpdns.org")
    assert rep["ns_delegated"] is True
    assert rep["spf"] is True
    assert rep["dkim"] is True
    assert rep["dmarc"] is True
    assert rep["overall"] == "ok", rep


def test_validate_missing_domain():
    rep = freedomain.validate("")
    assert rep["overall"] == "missing"
    assert rep["notes"]
