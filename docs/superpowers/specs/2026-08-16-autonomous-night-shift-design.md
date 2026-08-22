# LucidFence Autonomous Night Shift — Design

**Date:** 2026-08-16  
**Status:** Approved for specification review  
**Owner:** Adrián Martínez García  
**Repository baseline:** `adrimg3196/lucidfence@df076ee6099ecf2dec37d0c4717ff97818e0aa37`  
**Agency baseline:** `msitarzewski/agency-agents@ebe9c99acb5c96f9468de368d8bead775387d1a7`

## 1. Goal

Turn LucidFence into an unattended overnight software company. It must inspect the product and its GitHub ecosystem, choose valuable work, implement and verify at most two objectives per night, merge verified code and releases without routine human approval, and deliver one business-language executive report at 07:33 Europe/Madrid.

The human owner must not need to read code, logs, pull requests, or workflow output to understand what changed.

## 2. Scope

The night shift may autonomously:

- change application code, tests, architecture, documentation and workflows;
- update dependencies and dependency locks;
- resolve merge conflicts, deduplicate pull requests and drain the backlog;
- merge structural and security-sensitive code after the enhanced automated gates pass;
- publish releases and update packaging when release consistency checks pass;
- inspect current GitHub projects and use verified patterns to propose original improvements.

The night shift must never:

- execute `wipe`, `factory_reset`, device deletion, tenant deletion or device lock against a real fleet;
- weaken or disable audit, secret scanning, rollback, authentication or the safety policy;
- create, expose, rotate or repurpose credentials;
- introduce a paid dependency, paid API or mandatory hosted service;
- copy third-party code without a compatible licence and attribution;
- publish real tenant or device data;
- make claims about traction, tests or production readiness without evidence.

These restrictions are immutable from an autonomous cycle.

## 3. Integration of Agency Agents

The full upstream repository is used as a versioned capability catalogue rather than loading every persona into one prompt.

### Source contract

- Store the upstream repository, commit SHA, tree SHA and licence in `config/agency-agents.lock.json`.
- Check out the complete pinned repository during deterministic GitHub workflows.
- Build `data/agency_catalog.json` from every valid agent frontmatter file.
- Reject duplicate agent names, invalid frontmatter, missing divisions, unknown files and licence changes.
- The initial expected baseline is 264 agent profiles across 17 divisions.
- A daily upstream check may update the pin only through the same test, security and licence gates as product code.

### Runtime selection

Mission Control scores every profile against the objective and selects a squad of 3–7 roles. Every squad must include:

1. one business or product owner;
2. one domain specialist, normally GIS or UEM;
3. one implementation specialist;
4. one independent verifier.

Security-sensitive changes also require Application Security Engineer. User-facing changes require Reality Checker. The maker and final verifier must be different roles.

The selected profile files are fetched at the pinned commit, recorded in the run manifest and treated as advisory methods. LucidFence policy remains the final authority.

## 4. Operating Model

```text
GitHub state + product evidence + trend snapshots
                    |
                    v
             Mission Control
                    |
          objective selection (max 2)
                    |
                    v
        dynamic Agency Agents squad
                    |
           isolated branch and PR
                    |
       CI -> GIS QA -> AppSec -> Reality
                    |
          fix loop, maximum 3 passes
                    |
          merge -> verify main -> release
                    |
           07:33 executive report
```

Durable state lives in the repository, not in chat memory:

- `data/night_shift/runs/<date>.json`: objectives, squad, evidence and outcome;
- `data/night_shift/trends.jsonl`: daily GitHub measurements;
- `docs/internal/exec/<date>.md`: executive report;
- `docs/internal/loop-run-log.md`: compact operational record.

Runtime-generated state must be bounded, append-safe and contain no secrets or tenant data.

## 5. Nightly Schedule

All schedules use the IANA timezone `Europe/Madrid` and non-zero minutes.

| Time | Stage | Responsibility |
|---|---|---|
| 00:17 | Direction | Inspect main, issues, PRs, CI, releases and trends; choose up to two objectives |
| 00:47 | Build | Create isolated branches, implement changes and open PRs |
| 03:17 | Verify | Run independent QA, GIS and AppSec review; repair failures |
| 05:47 | Finalize | Rebase, merge, verify main, rollback failures and publish eligible releases |
| 07:33 | Executive | Deliver one business-language report through ChatGPT |

ChatGPT scheduled tasks provide the reasoning and use the connected GitHub plugin. GitHub Actions provide deterministic validation and repository-side safety. The repository-specific `loop_improve.py` remains the local evaluation loop. `/goal` provides an on-demand, long-running equivalent for manual starts.

All stages use one repository-wide concurrency group. A stage that finds an earlier stage still active records a skip rather than creating parallel conflicting work.

## 6. Work Selection

Mission Control applies this order:

1. restore a failing `main`;
2. repair or rollback a failed post-merge validation;
3. fix security findings with a reproducible test;
4. drain stale, conflicting or duplicate PRs;
5. fix verified product defects;
6. complete an existing roadmap objective;
7. adopt a trend-derived improvement.

No new trend-derived feature begins while more than three non-draft PRs are blocked or unmergeable. A night may select at most two objectives and only one may be a new feature.

## 7. GitHub Trend Scout

The scout tracks relevant repositories in geofencing, device management, Apple MDM, Android Enterprise, Windows management, osquery, GitOps and autonomous software delivery.

A candidate score combines:

- relevance to LucidFence and administrators;
- 7-day and 30-day star growth from stored snapshots;
- release and commit recency;
- issue and contributor activity;
- evidence of a real user problem;
- licence compatibility;
- implementation cost, operational cost and privacy impact.

The first observation is labelled “baseline”, never “trending”. Absolute stars alone do not establish a trend.

Trend-derived work must:

- cite the repositories and evidence that inspired it;
- describe the customer and business value;
- implement an original solution compatible with LucidFence architecture;
- avoid paid SDKs, mandatory cloud services and invasive telemetry;
- include tests and a rollback path.

The first validated candidate is accuracy-aware geofencing with boundary hysteresis to reduce false enter/exit events. It remains queued behind the current blocked PR backlog. The coordinate-`0.0` defect is already fixed on `main`; the night shift must verify its regression coverage and close the stale issue rather than duplicate the implementation.

## 8. Automated Merge Gates

A PR may merge without human approval only when all applicable gates pass:

1. branch is based on current `main` and has no unresolved conflicts;
2. change has one declared objective and bounded scope;
3. full repository tests pass on Python 3.11;
4. runtime battery and affected integration tests pass;
5. secret scan, dependency audit, licence scan and generated-artifact checks pass;
6. AppSec reports no unresolved critical or high finding;
7. GIS QA validates affected geometry, coordinates and boundary cases;
8. Reality Checker finds evidence for every user-facing claim;
9. a different role from the maker performs final review;
10. merge-train confirms no overlapping open PR owns the same files or issue.

Dependency, authentication, packaging and architecture changes require two independent successful verification passes. They no longer require routine human approval under autonomy mode B.

A maximum of three repair passes is allowed per objective. After that, the PR remains open, is labelled `night-shift-blocked`, and the executive report explains the business impact.

## 9. Merge, Release and Recovery

- Use squash merge and retain a run manifest linking objective, source evidence, squad and checks.
- Verify `main` after every merge with CI plus the runtime battery.
- If new failures appear, create and merge an automated revert before any other work.
- Never rewrite or force-push `main`.
- Release only when semantic version classification, changelog, package metadata, Homebrew formula and published artefacts agree.
- A release failure does not roll back healthy product code; it creates a bounded packaging repair objective.

Repository settings or permissions that prevent an authorised merge are reported as configuration blockers. The automation must not bypass branch protection.

## 10. Executive Report

The 07:33 report uses business language and this fixed order:

1. three-sentence summary;
2. new customer or administrator capabilities;
3. defects corrected and who they affected;
4. commercial impact and differentiation;
5. quality and security traffic light;
6. releases, documentation and demos;
7. plan for the next night;
8. exceptional blockers only.

Technical details and PR links are optional drill-down material. Metrics without a previous observation are reported as a first measurement, not a delta.

If nothing material changed, the report says so briefly and explains whether the reason was “nothing valuable”, “quality gate blocked”, or “platform unavailable”.

## 11. Skill and Automation Boundary

Create a personal skill named `lucidfence-night-shift` that contains the repeatable orchestration method, risk policy, role selection, GitHub workflow and executive-report contract. Scheduled task prompts explicitly invoke `$lucidfence-night-shift`.

The skill does not contain credentials or mutable project state. Project truth remains in LucidFence. The connected GitHub plugin is the only external write surface required for nightly work.

Create four scheduled tasks:

- Night Shift Direction and Build — 00:17;
- Night Shift Verification — 03:17;
- Night Shift Finalize — 05:47;
- LucidFence Executive Brief — 07:33.

The 00:47 build transition is performed within the first scheduled run after the direction manifest is committed, avoiding a fifth active task.

## 12. Acceptance Criteria

The design is complete when implementation demonstrates all of the following:

- catalogue validation finds exactly the complete pinned upstream agent set and all divisions;
- a test objective selects 3–7 appropriate roles and records the exact pinned sources;
- no prompt or workflow can authorize forbidden fleet actions;
- the existing coordinate-`0.0` fix is verified by regression tests and its stale issue is closed;
- the current PR backlog is inventoried and overlapping AMAPI work is identified before new feature creation;
- trend snapshots distinguish baseline from measured growth;
- a dry run produces a business-language report without unsupported claims;
- a synthetic failing PR is not merged;
- a synthetic passing change traverses all gates;
- a simulated post-merge regression produces an automated revert plan;
- all existing tests and new night-shift tests pass;
- the four scheduled tasks are created and enabled in `Europe/Madrid`;
- a second on-demand pass reports the updated state and the next selected objective.

## 13. Initial Rollout

1. Add the pinned catalogue and validation tooling.
2. Add Mission Control, trend snapshots, squad selection and run manifests.
3. Add merge gates, repair budget, release validation and rollback.
4. Create and validate the personal skill.
5. Install the four scheduled tasks.
6. Run one on-demand dry pass.
7. Run one bounded live pass that verifies and closes the stale coordinate-`0.0` issue, or selects the next smallest verified defect, but may not execute fleet actions.
8. Deliver the resulting executive report.
