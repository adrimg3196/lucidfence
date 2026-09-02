"""Issue #248 — local crypto-agility / post-quantum readiness (read-only).

Acceptance criteria exercised:
  * Fixtures cover RSA/ECC classical, ML-KEM/ML-DSA PQC, hybrid config, and
    unknown (no-signal) — the taxonomy the issue requires.
  * Each classification links the NIST-oriented RULE applied and the observed
    evidence (rule_id + evidence in the output).
  * Absence of inventory does NOT improve the readiness score (unknown lowers
    coverage and is never counted as ready).
  * Output contains a PROPOSED remediation/research plan that is never executed.
  * Tests guarantee no private/secret material is ever persisted by the model.
"""
from lucidfence.core.crypto_agility import (
    ingest,
    classify,
    readiness_score,
    proposed_remediation,
    device_posture,
    load_fixture,
    CryptoEvidence,
    CryptoClass,
    SignalFreshness,
    RULES_VERSION,
)


def test_rsa_is_quantum_vulnerable_with_rule_citation():
    recs = load_fixture("rsa_cert_fresh")
    cls, rule_id = classify(recs[0])
    assert cls is CryptoClass.QUANTUM_VULNERABLE
    assert rule_id.startswith("rule:classical-qv:")


def test_ecc_is_quantum_vulnerable():
    recs = load_fixture("ecc_key_fresh")
    cls, rule_id = classify(recs[0])
    assert cls is CryptoClass.QUANTUM_VULNERABLE
    assert rule_id.startswith("rule:classical-qv:")


def test_mlkem_is_pqc_ready():
    recs = load_fixture("mlkem_fresh")
    cls, rule_id = classify(recs[0])
    assert cls is CryptoClass.PQC_READY
    assert rule_id.startswith("rule:pqc-family:")


def test_mldsa_is_pqc_ready():
    recs = load_fixture("mldsa_fresh")
    cls, rule_id = classify(recs[0])
    assert cls is CryptoClass.PQC_READY


def test_hybrid_device_posture_detected():
    # dev-d1 carries both RSA (classical-QV) and ML-KEM (PQC) -> HYBRID.
    recs = load_fixture("hybrid_device")
    posture = device_posture(recs)
    assert posture["dev-d1"]["posture"] == CryptoClass.HYBRID.value
    assert posture["dev-d1"]["rules_version"] == RULES_VERSION


def test_no_signal_is_unknown_not_ready():
    recs = load_fixture("no_signal_unknown")
    cls, rule_id = classify(recs[0])
    assert cls is CryptoClass.UNKNOWN
    assert rule_id.startswith("rule:no-signal:")
    # readiness must NOT count unknown as ready
    score = readiness_score(recs)
    assert score["ready_artifacts"] == 0
    assert score["readiness_percent"] == 0
    assert score["coverage_percent"] == 0  # no signal => 0 coverage


def test_absence_does_not_inflate_readiness():
    # A fleet with one unknown artifact must score 0 readiness, not 100.
    recs = load_fixture("no_signal_unknown")
    score = readiness_score(recs)
    assert score["readiness_percent"] == 0


def test_stale_data_flagged_stale_but_classified():
    recs = load_fixture("stale_rsa")
    r = recs[0]
    assert r.freshness() == SignalFreshness.STALE
    cls, _ = classify(r)
    assert cls is CryptoClass.QUANTUM_VULNERABLE  # still classifiable


def test_proposed_remediation_is_never_executed():
    recs = load_fixture("rsa_cert_fresh") + load_fixture("ecc_key_fresh") + \
        load_fixture("mlkem_fresh")
    plan = proposed_remediation(recs)
    # Only the QV artifacts get a plan item, not the PQC-ready one.
    assert len(plan) == 2
    for item in plan:
        assert item["classification"] == CryptoClass.QUANTUM_VULNERABLE.value
        assert item["executed"] is False
        assert "NOT executed" in item["action"]
        # evidence links the observation to the rule
        assert "rule_id" in item and item["rule_id"]


def test_classification_links_rule_and_evidence():
    recs = load_fixture("rsa_cert_fresh")
    cls, rule_id = classify(recs[0])
    plan = proposed_remediation(recs)
    assert plan[0]["rule_id"] == rule_id
    assert plan[0]["evidence"]["algorithm"] == "rsa"


def test_no_private_material_persisted():
    # The model must refuse to persist anything that looks like secret material.
    bad = [
        {
            "device_id": "x",
            "platform": "ios",
            "source": "private_key_export",
            "method": "leak",
            "artifact": "key",
            "algorithm": "private_key",
        }
    ]
    out = ingest(bad)
    assert out == []  # dropped, never persisted

    # And the dataclass itself must not carry forbidden fields.
    fields = set(CryptoEvidence.__dataclass_fields__.keys())
    forbidden = {"private_key", "secret", "token", "password", "key_material"}
    assert forbidden.isdisjoint(fields)


def test_discovery_signal_distinguished():
    # observed vs inferred is preserved for auditability.
    recs = load_fixture("rsa_cert_fresh")
    assert recs[0].discovery == "observed"
    # an inferred record keeps inferred
    inferred = ingest(
        [{"device_id": "z", "platform": "ios", "source": "fixture",
          "method": "guess", "artifact": "tls", "algorithm": "rsa"}]
    )
    assert inferred[0].discovery == "inferred"
