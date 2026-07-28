# Enterprise pilot runbook

## Entry criteria

- Named business owner, security owner and rollback approver.
- Written scope: tenant, device cohort, geofences, permitted actions and data retention.
- Dry-run enabled; production credentials entered only in the local tenant settings.
- Baseline backup and `lucidfence doctor` PASS.

## 30-day pilot

### Week 0 — readiness

1. Run `python3 tests/run_tests.py`, gitleaks, pip-audit and SBOM generation.
2. Create a dedicated pilot tenant and auditor account.
3. Import 5–20 non-critical devices; keep destructive commands disabled.
4. Confirm location consent, employee notice and retention policy.

### Week 1 — observe

Record location signal coverage, false geofence events, CVE inventory coverage and time-to-detection. Do not auto-remediate.

### Week 2 — tune

Tune radius/corridor, cooldown and alert routing. Every change must appear in the audit trail. Target false-positive rate below 5%.

### Week 3 — controlled remediation

Enable one reversible action for an approved cohort. Require named operator and rollback. Compare dry-run recommendation against executed action.

### Week 4 — decision

Export compliance, incidents and audit evidence. Review success metrics and record a go/no-go decision.

## Success metrics

| Metric | Baseline | Target |
|---|---:|---:|
| Inventory coverage | measured day 1 | ≥98% |
| Valid location signal | measured day 1 | ≥95% |
| False-positive geofence events | measured week 1 | <5% |
| Mean time to acknowledge critical incident | measured week 1 | <15 min |
| Reversible remediation success | n/a | ≥95% |
| Cross-tenant data exposure | 0 | 0 |

## ROI worksheet

Monthly benefit = incidents avoided × average incident cost + analyst hours saved × loaded hourly cost. Pilot cost includes operator time, infrastructure and UEM licensing already owned. Report assumptions and ranges; never invent savings.

## Rollback and exit

Disable automation, revoke tenant API keys, export audit evidence, restore the pre-pilot backup if required, remove pilot device assignments and confirm data retention/deletion with the owner. Severity-1 response target: acknowledge 15 minutes, contain 60 minutes; all other support is best-effort unless a signed SLA says otherwise.
