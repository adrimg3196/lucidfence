# Spec Template — Mini-SDD for LucidFence Features

Use this template when proposing a new feature or significant change to LucidFence. It follows a lightweight Systematic Design Discipline (SDD) approach: just enough design to align before implementation, not so much that it becomes bureaucracy.

## 1. Problem statement

**What is the problem?** (1-3 sentences, plain language)

**Who feels it?** (operators, developers, users — be specific)

**How do we know it's real?** (evidence: issue, user report, operational pain, measurable gap)

---

## 2. Scope

### In scope

- What this feature covers
- What problem it solves

### Out of scope

- What this feature explicitly does NOT cover
- What's deferred to a later iteration

---

## 3. Proposed solution

### Summary

1-3 sentences describing what we build and how it solves the problem.

### Design

- **Architecture:** Which components are involved? New modules? Changes to existing ones?
- **Interfaces:** What new APIs, CLI commands, config keys, or UI elements are introduced?
- **Data model:** Any new state, fields, or schemas?
- **Integration points:** Adapters, UEMs, other systems affected?

### Alternatives considered

List 2-3 alternatives and why they were not chosen. This section is important — it shows the decision is deliberate, not arbitrary.

---

## 4. Implementation plan

### Steps

Break the implementation into discrete, testable steps. Each step should be small enough to review independently.

Example:

1. Step 1: Create `lucidfence/core/new_module.py` with X
2. Step 2: Add unit tests in `tests/test_new_module.py`
3. Step 3: Wire into CLI as `lucidfence command`
4. Step 4: Update docs

### Testing strategy

- **Unit tests:** What to test in isolation
- **Integration tests:** What to test end-to-end
- **Runtime validation:** What the runtime battery should cover (see `scripts/runtime_validation.py`)
- **Baseline:** Any known limitations or environments where tests may not pass

---

## 5. Verification

### Definition of done

- [ ] Code implemented and tested
- [ ] Tests pass (`.venv/bin/python tests/run_tests.py` green)
- [ ] Runtime battery passes (`.venv/bin/python scripts/verify.py --fast` green)
- [ ] Docs updated (this spec, plus any user-facing docs)
- [ ] CLI or API interface documented
- [ ] No secrets in code, config, or docs
- [ ] `verify.py` fully green (all 4 checks)

### Acceptance criteria

- **Criterion 1:** [Specific, measurable condition]
- **Criterion 2:** [Specific, measurable condition]
- **Criterion N:** [...]

---

## 6. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Example: breaks existing adapter contract | Medium | High | Test against all registered adapters; add regression test |
| ... | ... | ... | ... |

---

## 7. Dependencies

- **Code dependencies:** New modules, changes to existing modules
- **Documentation dependencies:** Docs that need updating
- **External dependencies:** UEM APIs, third-party services (NONE if possible — see Constitution Article II)
- **Human dependencies:** Decisions that need owner input (outreach, partnerships)

---

## 8. Rollback plan

If this change needs to be reverted:

1. How to revert (git revert, feature flag, config toggle)
2. What state is preserved / lost on revert
3. How to verify the revert is clean

---

## 9. Sign-off

- **Author:** [Name]
- **Reviewer:** [Name / role]
- **CTO co-sign (if GTM/claims):** [Yes/No — required for any user-facing claim]
- **Date:** [YYYY-MM-DD]

---

## Example: filled template

See any completed spec in `docs/superpowers/plans/` for a real example of this template filled out.

## Process notes

- This template lives at `docs/internal/product/spec-template.md`
- Completed specs go in `docs/internal/product/` with descriptive filenames
- The roadmap (`docs/roadmap/PRODUCT_ROADMAP.md`) references specs that are approved
- Specs are living documents — update them as implementation reveals new information
- Specs are not contracts; they're alignment tools. Deviation is fine if documented.
