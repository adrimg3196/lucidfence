# Autonomous Night Shift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the complete pinned Agency Agents catalogue with LucidFence, operate a safe unattended overnight development loop, and deliver a business-language morning brief.

**Architecture:** ChatGPT scheduled tasks and the GitHub plugin perform reasoning and repository mutations. LucidFence stores durable manifests, trend history and deterministic merge evidence; GitHub Actions validates the complete pinned upstream catalogue, tests product changes and watches the night-shift state. The full catalogue remains pinned upstream and is checked out in workflows, while a compact generated index allows deterministic role selection.

**Tech Stack:** Python 3.11, LucidFence zero-dependency test runner, GitHub Actions, GitHub plugin, ChatGPT Scheduled Tasks, Codex personal skills.

## Global Constraints

- Repository: `adrimg3196/lucidfence`; default branch: `main`.
- Agency source: `msitarzewski/agency-agents@ebe9c99acb5c96f9468de368d8bead775387d1a7`.
- Expected source inventory: 264 agent profiles across 17 divisions.
- Maximum two objectives per night; maximum one new feature.
- Use `Europe/Madrid` for every schedule.
- Never execute destructive actions against real devices or tenants.
- Never introduce secrets, paid dependencies, mandatory hosted services or real tenant data.
- Keep Python runtime code stdlib-first and compatible with Python 3.11.
- Run `python3 tests/run_tests.py` and `python3 scripts/runtime_validation.py` before completion.
- Do not modify `data/cloud_state.json` from a feature branch.
- Use isolated branches; never edit the shared checkout or force-push `main`.

---

## File Map

- `config/agency-agents.lock.json` — immutable upstream source contract.
- `lucidfence/core/agency_catalog.py` — catalogue discovery, validation and deterministic JSON generation.
- `scripts/agency_catalog.py` — command-line interface used by CI.
- `data/agency_catalog.json` — compact generated index; no copied prompts.
- `lucidfence/core/night_shift.py` — objectives, squad selection and run manifests.
- `lucidfence/core/trend_scout.py` — honest baseline and 7/30-day trend scoring.
- `scripts/night_shift.py` — deterministic stage CLI for direction, verification and reporting.
- `lucidfence/core/loop_governance.py` — autonomy-B evidence gate and forbidden-action policy.
- `.agents/skills/lucidfence-night-shift/` — repository-owned source for the repeatable skill.
- `.github/workflows/agency-catalog.yml` — full upstream catalogue validation.
- `.github/workflows/night-shift-watchdog.yml` — scheduled-state watchdog and report artefact.
- `docs/internal/NIGHT_SHIFT_GOAL.md` — on-demand `/goal` contract.
- `docs/internal/loop-constraints.md` and `AGENTS.md` — autonomy-B governance.
- `tests/test_agency_catalog.py` — catalogue contract tests.
- `tests/test_night_shift.py` — squad, manifest and report tests.
- `tests/test_trend_scout.py` — baseline and trend maths tests.
- `tests/test_loop_governance.py` — merge and forbidden-action tests.

---

### Task 1: Pin and validate the complete Agency Agents catalogue

**Files:**
- Create: `config/agency-agents.lock.json`
- Create: `lucidfence/core/agency_catalog.py`
- Create: `scripts/agency_catalog.py`
- Create: `tests/test_agency_catalog.py`
- Generate: `data/agency_catalog.json`

**Interfaces:**
- Produces: `AgencyLock.from_path(path: Path) -> AgencyLock`
- Produces: `discover_agents(source: Path) -> list[AgentProfile]`
- Produces: `build_catalog(source: Path, lock: AgencyLock) -> dict`
- Produces CLI: `python3 scripts/agency_catalog.py --source PATH --lock PATH --output PATH [--check]`

- [ ] **Step 1: Write failing lock and discovery tests**

```python
def test_catalog_discovers_every_frontmatter_agent(tmp_path):
    source = tmp_path / "agency"
    (source / "gis").mkdir(parents=True)
    (source / "engineering").mkdir()
    (source / "gis" / "gis-qa.md").write_text(
        "---\nname: GIS QA Engineer\ndescription: Validates spatial evidence.\n---\n# Body\n",
        encoding="utf-8",
    )
    (source / "engineering" / "backend.md").write_text(
        "---\nname: Backend Architect\ndescription: Designs reliable services.\n---\n# Body\n",
        encoding="utf-8",
    )
    profiles = discover_agents(source)
    assert [(p.division, p.name) for p in profiles] == [
        ("engineering", "Backend Architect"),
        ("gis", "GIS QA Engineer"),
    ]

def test_catalog_rejects_count_or_division_drift(tmp_path):
    lock = AgencyLock(
        repository="msitarzewski/agency-agents",
        commit="ebe9c99acb5c96f9468de368d8bead775387d1a7",
        license_spdx="MIT",
        expected_agents=264,
        expected_divisions=17,
    )
    try:
        validate_inventory([], lock)
        raise AssertionError("inventory drift was accepted")
    except ValueError as exc:
        assert "expected 264 agents" in str(exc)
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run: `python3 -c "import tests.test_agency_catalog as t; t.test_catalog_discovers_every_frontmatter_agent(__import__('pathlib').Path('/tmp/not-used'))"` is not used because the repository runner owns temporary setup.  
Run: `python3 tests/run_tests.py`  
Expected: FAIL importing `lucidfence.core.agency_catalog`.

- [ ] **Step 3: Implement immutable data types and frontmatter discovery**

```python
@dataclass(frozen=True)
class AgencyLock:
    repository: str
    commit: str
    license_spdx: str
    expected_agents: int
    expected_divisions: int

@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    division: str
    path: str
    sha256: str

def discover_agents(source: Path) -> list[AgentProfile]:
    profiles = []
    for path in sorted(source.glob("*/*.md")):
        fields = parse_frontmatter(path.read_text(encoding="utf-8"))
        if "name" not in fields or "description" not in fields:
            continue
        profiles.append(AgentProfile(
            name=fields["name"],
            description=fields["description"],
            division=path.parent.name,
            path=path.relative_to(source).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ))
    return profiles
```

The parser must accept only the first YAML frontmatter block and simple scalar values; it must not execute YAML tags.

- [ ] **Step 4: Add the exact lock file**

```json
{
  "repository": "msitarzewski/agency-agents",
  "commit": "ebe9c99acb5c96f9468de368d8bead775387d1a7",
  "license_spdx": "MIT",
  "expected_agents": 264,
  "expected_divisions": 17
}
```

- [ ] **Step 5: Generate and validate the real compact catalogue**

Run:
```bash
git clone --filter=blob:none --no-checkout https://github.com/msitarzewski/agency-agents.git /tmp/lucidfence-agency-agents
git -C /tmp/lucidfence-agency-agents checkout ebe9c99acb5c96f9468de368d8bead775387d1a7
python3 scripts/agency_catalog.py --source /tmp/lucidfence-agency-agents --lock config/agency-agents.lock.json --output data/agency_catalog.json
python3 scripts/agency_catalog.py --source /tmp/lucidfence-agency-agents --lock config/agency-agents.lock.json --output data/agency_catalog.json --check
```
Expected: 264 agents, 17 divisions, no duplicate names or hash mismatch.

- [ ] **Step 6: Run all tests**

Run: `python3 tests/run_tests.py`  
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add config/agency-agents.lock.json lucidfence/core/agency_catalog.py scripts/agency_catalog.py tests/test_agency_catalog.py data/agency_catalog.json
git commit -m "feat: pin complete agency agent catalogue"
```

---

### Task 2: Add deterministic squad selection and run manifests

**Files:**
- Create: `lucidfence/core/night_shift.py`
- Create: `tests/test_night_shift.py`

**Interfaces:**
- Consumes: `AgentProfile` from Task 1.
- Produces: `Objective(id: str, title: str, evidence: tuple[str, ...], keywords: tuple[str, ...])`
- Produces: `select_squad(objective: Objective, profiles: list[AgentProfile]) -> tuple[AgentProfile, ...]`
- Produces: `write_run_manifest(root: Path, manifest: NightShiftManifest) -> Path`

- [ ] **Step 1: Write failing squad tests**

```python
def test_squad_has_business_domain_builder_and_independent_verifier():
    profiles = fixture_profiles()
    objective = Objective(
        id="geo-boundary",
        title="Reduce false geofence transitions",
        evidence=("Tile38 boundary model", "support reports"),
        keywords=("gis", "geofence", "backend", "quality"),
    )
    squad = select_squad(objective, profiles)
    names = {p.name for p in squad}
    assert 3 <= len(squad) <= 7
    assert "Product Manager" in names
    assert "GIS QA Engineer" in names
    assert "Backend Architect" in names
    assert "Reality Checker" in names
    assert len({p.path for p in squad}) == len(squad)

def test_security_change_requires_appsec():
    objective = Objective("auth", "Harden API authentication", ("finding-1",), ("auth", "security"))
    names = {p.name for p in select_squad(objective, fixture_profiles())}
    assert "Application Security Engineer" in names
```

- [ ] **Step 2: Verify the tests fail**

Run: `python3 tests/run_tests.py`  
Expected: FAIL importing `lucidfence.core.night_shift`.

- [ ] **Step 3: Implement scored selection with mandatory seats**

Use normalized tokens from objective title, keywords, profile name, description and division. Fill mandatory seats first, then add the highest-scoring distinct profiles until the squad has at least four members. Stable-sort by `(-score, division, name)`; never use randomness.

- [ ] **Step 4: Implement atomic, secret-safe manifests**

```python
FORBIDDEN_KEYS = {"token", "secret", "password", "authorization", "api_key"}

def write_run_manifest(root: Path, manifest: NightShiftManifest) -> Path:
    payload = asdict(manifest)
    reject_forbidden_keys(payload, FORBIDDEN_KEYS)
    target = root / "data" / "night_shift" / "runs" / f"{manifest.date}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target
```

- [ ] **Step 5: Test deterministic output and secret rejection**

Run: `python3 tests/run_tests.py`  
Expected: all tests PASS, including identical squads across repeated calls and rejection of nested secret keys.

- [ ] **Step 6: Commit**

```bash
git add lucidfence/core/night_shift.py tests/test_night_shift.py
git commit -m "feat: select and record night shift squads"
```

---

### Task 3: Build the honest GitHub trend scout

**Files:**
- Create: `lucidfence/core/trend_scout.py`
- Create: `tests/test_trend_scout.py`
- Create: `data/night_shift/trends.jsonl`

**Interfaces:**
- Produces: `RepoObservation(repository, observed_at, stars, forks, open_issues, pushed_at, releases_30d, commits_30d)`
- Produces: `append_observations(path: Path, observations: Iterable[RepoObservation]) -> None`
- Produces: `score_trends(history: list[RepoObservation], now: datetime) -> list[TrendCandidate]`

- [ ] **Step 1: Write failing baseline and delta tests**

```python
def test_first_observation_is_baseline_not_trending(tmp_path):
    observation = RepoObservation("tidwall/tile38", "2026-08-16T00:17:00Z", 9714, 621, 100, "2026-08-07T12:16:28Z", 1, 20)
    candidates = score_trends([observation], now=parse_time("2026-08-16T00:17:00Z"))
    assert candidates[0].status == "baseline"
    assert candidates[0].star_growth_7d is None

def test_growth_requires_two_time_points():
    history = [
        RepoObservation("example/geo", "2026-08-09T00:17:00Z", 100, 10, 4, "2026-08-09T00:00:00Z", 0, 2),
        RepoObservation("example/geo", "2026-08-16T00:17:00Z", 125, 12, 5, "2026-08-16T00:00:00Z", 1, 14),
    ]
    candidate = score_trends(history, now=parse_time("2026-08-16T00:17:00Z"))[0]
    assert candidate.status == "measured"
    assert candidate.star_growth_7d == 25
```

- [ ] **Step 2: Verify the tests fail**

Run: `python3 tests/run_tests.py`  
Expected: FAIL importing `lucidfence.core.trend_scout`.

- [ ] **Step 3: Implement append-only snapshots and scoring**

The score must combine normalized relevance, star growth, release activity, commit activity and licence compatibility. A single observation always returns `status="baseline"`. Missing metrics remain `None` and are never estimated.

- [ ] **Step 4: Seed the first measured repositories**

Seed only public metadata already verified during the manual pass:

```text
msitarzewski/agency-agents
tidwall/tile38
fleetdm/fleet
micromdm/nanomdm
transistorsoft/flutter_background_geolocation
radarlabs/radar-sdk-ios
```

Do not label any baseline entry as trending.

- [ ] **Step 5: Run tests and commit**

Run: `python3 tests/run_tests.py`  
Expected: all tests PASS.

```bash
git add lucidfence/core/trend_scout.py tests/test_trend_scout.py data/night_shift/trends.jsonl
git commit -m "feat: add evidence-based GitHub trend scout"
```

---

### Task 4: Implement autonomy-B merge evidence

**Files:**
- Modify: `lucidfence/core/loop_governance.py`
- Modify: `tests/test_loop_governance.py`

**Interfaces:**
- Preserves: `verify_twice` and `gated_merge` for legacy loops.
- Produces: `GateCheck(name: str, passed: bool, reviewer_role: str, evidence: str)`
- Produces: `evaluate_night_shift_gate(paths: list[str], checks: list[GateCheck], actions: list[str]) -> NightShiftVerdict`
- Produces: `NightShiftVerdict(auto_merge: bool, risk: str, blockers: tuple[str, ...])`

- [ ] **Step 1: Add failing evidence-gate tests**

```python
def test_autonomy_b_high_risk_requires_two_independent_security_reviews():
    checks = passing_gate_checks() + [
        GateCheck("appsec-primary", True, "Application Security Engineer", "scan-a"),
        GateCheck("appsec-secondary", True, "Security Architect", "scan-b"),
    ]
    verdict = evaluate_night_shift_gate(["lucidfence/saas/auth.py"], checks, [])
    assert verdict.risk == "high"
    assert verdict.auto_merge is True

def test_same_reviewer_cannot_supply_both_security_passes():
    checks = passing_gate_checks() + [
        GateCheck("appsec-primary", True, "Application Security Engineer", "scan-a"),
        GateCheck("appsec-secondary", True, "Application Security Engineer", "scan-b"),
    ]
    verdict = evaluate_night_shift_gate(["lucidfence/saas/auth.py"], checks, [])
    assert verdict.auto_merge is False
    assert "independent security reviewers required" in verdict.blockers

def test_forbidden_fleet_action_can_never_merge():
    verdict = evaluate_night_shift_gate(["lucidfence/core/actions.py"], passing_gate_checks(), ["factory_reset"])
    assert verdict.auto_merge is False
    assert "forbidden action: factory_reset" in verdict.blockers
```

- [ ] **Step 2: Verify the tests fail**

Run: `python3 tests/run_tests.py`  
Expected: FAIL because `GateCheck` and `evaluate_night_shift_gate` do not exist.

- [ ] **Step 3: Implement required check sets**

Required names for every code change:

```python
BASE_REQUIRED = {
    "ci", "runtime", "secrets", "dependencies",
    "license", "appsec", "reality", "overlap",
}
FORBIDDEN_ACTIONS = {
    "wipe", "factory_reset", "delete_device", "delete_tenant",
    "request_device_lock", "disable_audit",
}
```

High-risk changes additionally require `appsec-primary` and `appsec-secondary` with distinct reviewer roles. Every required check must pass and include non-empty evidence.

- [ ] **Step 4: Preserve the legacy gate tests**

Run: `python3 tests/run_tests.py`  
Expected: original low-risk `verify_twice` tests and all new autonomy-B tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lucidfence/core/loop_governance.py tests/test_loop_governance.py
git commit -m "feat: enforce autonomy B merge evidence"
```

---

### Task 5: Add the deterministic night-shift stage CLI

**Files:**
- Create: `scripts/night_shift.py`
- Modify: `tests/test_night_shift.py`

**Interfaces:**
- CLI: `python3 scripts/night_shift.py direction --input snapshot.json --catalog data/agency_catalog.json --date YYYY-MM-DD`
- CLI: `python3 scripts/night_shift.py verify --manifest PATH --evidence PATH`
- CLI: `python3 scripts/night_shift.py report --manifest PATH --output PATH`

- [ ] **Step 1: Write failing CLI contract tests**

Use `subprocess.run` with a temporary snapshot containing 13 blocked PRs, one green `main`, issue #87 marked open and one baseline trend observation. Assert that:

- direction chooses backlog drainage before a new trend feature;
- at most two objectives are emitted;
- issue #87 is classified as `verify_and_close_stale`;
- the executive report says “primera medición”, never “subiendo”, for baseline-only trends.

- [ ] **Step 2: Verify failure**

Run: `python3 tests/run_tests.py`  
Expected: FAIL because `scripts/night_shift.py` does not exist.

- [ ] **Step 3: Implement stage commands**

`direction` reads only structured evidence and produces a manifest. `verify` evaluates Task 4 gates. `report` renders the eight approved business sections. No command calls GitHub or executes UEM actions; external mutation remains in the GitHub plugin.

- [ ] **Step 4: Run tests and a fixture dry run**

```bash
python3 tests/run_tests.py
python3 scripts/night_shift.py direction --input tests/fixtures/night_shift_snapshot.json --catalog data/agency_catalog.json --date 2026-08-16
python3 scripts/night_shift.py report --manifest data/night_shift/runs/2026-08-16.json --output /tmp/lucidfence-exec.md
```

Expected: tests PASS; report contains TL;DR, new, corrected, commercial impact, quality, releases, next night and blockers.

- [ ] **Step 5: Commit**

```bash
git add scripts/night_shift.py tests/test_night_shift.py tests/fixtures/night_shift_snapshot.json
git commit -m "feat: add deterministic night shift stages"
```

---

### Task 6: Package the repository-owned night-shift skill

**Files:**
- Create: `.agents/skills/lucidfence-night-shift/SKILL.md`
- Create: `.agents/skills/lucidfence-night-shift/references/risk-policy.md`
- Create: `.agents/skills/lucidfence-night-shift/references/github-stages.md`
- Create: `.agents/skills/lucidfence-night-shift/references/executive-report.md`

**Interfaces:**
- Trigger: `$lucidfence-night-shift`
- Inputs: repository, stage, date and optional existing run manifest.
- Output: one structured stage result plus GitHub links for any mutation.

- [ ] **Step 1: Write the skill with four explicit stages**

The body must require:

1. fetch `AGENTS.md`, lock, catalogue, state, open PRs/issues and recent CI;
2. select the squad from exact pinned agent paths;
3. record evidence before mutation;
4. stop on forbidden device operations or missing credentials;
5. use the GitHub plugin for repository reads and writes;
6. return the executive contract for the `executive` stage.

- [ ] **Step 2: Add durable stage prompts**

`github-stages.md` must contain exact prompts for `direction-build`, `verify`, `finalize` and `executive`. Every prompt names `adrimg3196/lucidfence`, reads the latest run manifest and refuses unrelated repositories.

- [ ] **Step 3: Validate the repository skill**

Run:
```bash
python3 /root/.codex/skills/oai/skill-creator/scripts/quick_validate.py .agents/skills/lucidfence-night-shift
```
Expected: validation succeeds.

- [ ] **Step 4: Commit**

```bash
git add .agents/skills/lucidfence-night-shift
git commit -m "feat: package LucidFence night shift skill"
```

---

### Task 7: Add catalogue and watchdog workflows

**Files:**
- Create: `.github/workflows/agency-catalog.yml`
- Create: `.github/workflows/night-shift-watchdog.yml`
- Modify: `docs/internal/LOOP.md`
- Modify: `docs/internal/loop-constraints.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Catalogue validation workflow checks out LucidFence and the full pinned Agency Agents commit.
- Watchdog generates an artefact; it never merges or calls UEM.
- Governance documents declare autonomy B and immutable forbidden actions.

- [ ] **Step 1: Add the catalogue workflow**

```yaml
name: agency-catalog

on:
  pull_request:
    paths:
      - "config/agency-agents.lock.json"
      - "data/agency_catalog.json"
      - "lucidfence/core/agency_catalog.py"
      - "scripts/agency_catalog.py"
  schedule:
    - cron: "37 23 * * *"
      timezone: "Europe/Madrid"
  workflow_dispatch:

concurrency:
  group: lucidfence-night-shift
  cancel-in-progress: false

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          path: lucidfence
      - uses: actions/checkout@v4
        with:
          repository: msitarzewski/agency-agents
          ref: ebe9c99acb5c96f9468de368d8bead775387d1a7
          path: agency-agents
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python3 scripts/agency_catalog.py --source ../agency-agents --lock config/agency-agents.lock.json --output data/agency_catalog.json --check
        working-directory: lucidfence
```

- [ ] **Step 2: Add the watchdog workflow**

Schedule it at 06:47 Europe/Madrid. It runs `scripts/night_shift.py watchdog`, uploads `night-shift-watchdog.json`, and fails only for a stale active run, a missing finalization stage or a forbidden-action record.

- [ ] **Step 3: Update governance**

Replace routine human gates for code, dependencies, packaging and auth with the Task 4 evidence requirements. Preserve permanent denials for device destruction, secrets, new costs, audit weakening and real tenant data.

- [ ] **Step 4: Validate workflow syntax and full tests**

```bash
python3 tests/run_tests.py
python3 scripts/runtime_validation.py
python3 -c "import pathlib; [print(p) for p in pathlib.Path('.github/workflows').glob('*.yml')]"
```
Expected: all tests and runtime checks PASS; both workflows are present.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/agency-catalog.yml .github/workflows/night-shift-watchdog.yml docs/internal/LOOP.md docs/internal/loop-constraints.md AGENTS.md
git commit -m "feat: schedule deterministic night shift safeguards"
```

---

### Task 8: Install the personal skill

**Files:**
- Create outside the product repo: `/root/.codex/skills/remote-skills/lucidfence-night-shift/`

**Interfaces:**
- Personal skill name: `lucidfence-night-shift`
- Source of truth: repository skill from Task 6.

- [ ] **Step 1: Initialize the personal skill**

```bash
python3 /root/.codex/skills/oai/skill-creator/scripts/init_skill.py lucidfence-night-shift \
  --path /root/.codex/skills/remote-skills \
  --resources references \
  --interface display_name="LucidFence Night Shift" \
  --interface short_description="Runs the autonomous LucidFence overnight company." \
  --interface default_prompt="Use the LucidFence night shift workflow for the requested stage."
```

- [ ] **Step 2: Copy the validated instructions from Task 6**

Copy `SKILL.md` and the three reference files. Do not copy credentials, run manifests or repository data.

- [ ] **Step 3: Validate and save**

```bash
python3 /root/.codex/skills/oai/skill-creator/scripts/quick_validate.py /root/.codex/skills/remote-skills/lucidfence-night-shift
git -C /root/.codex/skills/remote-skills add lucidfence-night-shift
git -C /root/.codex/skills/remote-skills commit -m "Add LucidFence night shift skill"
git -C /root/.codex/skills/remote-skills push
```

Expected: the skill is installed and discoverable by its frontmatter name.

---

### Task 9: Create the four scheduled tasks

**Files:** none.

**Interfaces:** ChatGPT Scheduled Tasks with `default_timezone="Europe/Madrid"`.

- [ ] **Step 1: Test each stage prompt manually**

Run the four prompts once against `adrimg3196/lucidfence` without mutation. Confirm each reads GitHub successfully, uses the pinned catalogue and returns its expected stage output.

- [ ] **Step 2: Create Direction and Build**

Schedule:
```text
BEGIN:VEVENT
DTSTART:20260817T001700
RRULE:FREQ=DAILY
END:VEVENT
```

Prompt: `Use $lucidfence-night-shift for the direction-build stage on adrimg3196/lucidfence. Read durable repository state, select at most two objectives, create isolated branches and PRs, and never perform a forbidden fleet action.`

- [ ] **Step 3: Create Verification**

Schedule at `20260817T031700`, daily. Prompt invokes the `verify` stage, fixes failures for at most three passes and records evidence.

- [ ] **Step 4: Create Finalize**

Schedule at `20260817T054700`, daily. Prompt invokes the `finalize` stage, rebases, merges only passing verdicts, verifies `main`, reverts regressions and publishes eligible releases.

- [ ] **Step 5: Create Executive Brief**

Schedule at `20260817T073300`, daily. Prompt invokes the `executive` stage and returns only the approved business-language report plus optional drill-down links.

- [ ] **Step 6: Verify automation records**

Privately inspect the four task records. Confirm all are enabled, daily and use `Europe/Madrid`.

---

### Task 10: Publish the implementation PR and run the second pass

**Files:**
- Update: `docs/internal/loop-run-log.md`
- Create: `docs/internal/exec/2026-08-16-night-shift-test.md`

**Interfaces:**
- Implementation branch: `agent/autonomous-night-shift`
- Base: latest `main`
- PR title: `feat: run LucidFence as an autonomous night shift`

- [ ] **Step 1: Rebase onto current main and run verification**

```bash
git fetch origin main
git rebase origin/main
python3 tests/run_tests.py
python3 scripts/runtime_validation.py
python3 scripts/agency_catalog.py --source /tmp/lucidfence-agency-agents --lock config/agency-agents.lock.json --output data/agency_catalog.json --check
```

Expected: all commands PASS and the working tree contains no runtime snapshot changes.

- [ ] **Step 2: Verify issue #87 before closing**

Run the existing and new location-source regression tests with explicit nested and flat payloads containing `lat=0.0` and `lng=0.0`. Confirm `_coalesce` preserves zero. Add no duplicate implementation.

- [ ] **Step 3: Run an updated on-demand direction pass**

Fetch current PRs, issues, workflows, latest commits and trend observations. Expected priorities:

1. drain overlapping AMAPI PRs;
2. close stale issue #87 after evidence;
3. queue accuracy-aware boundary hysteresis only while blocked-PR count is at most three.

- [ ] **Step 4: Write the executive result**

The report must distinguish:

- infrastructure integrated;
- stale issue verified and closed;
- current PR backlog count and canonical AMAPI path;
- latest 30-workflow health;
- trend observations as baseline unless a second time point exists;
- quality verdict and next-night objective.

- [ ] **Step 5: Commit and open a draft PR**

```bash
git add docs/internal/loop-run-log.md docs/internal/exec/2026-08-16-night-shift-test.md
git commit -m "docs: record autonomous night shift validation"
git push -u origin agent/autonomous-night-shift
```

Open a draft PR through the GitHub plugin. Its body must list implementation, business impact, security boundaries, exact checks and the second-pass result.

- [ ] **Step 6: Request independent review**

Use the repository code-review and verification skills. Address findings, rerun the full suite and only then mark the PR ready.

---

## Plan Self-Review

- Every design requirement maps to a task.
- No task authorizes destructive fleet operations, secret creation or new spending.
- The complete upstream repository is used at a pinned commit without copying all prompts into LucidFence.
- The first trend snapshot is explicitly a baseline.
- Issue #87 is verified and closed as stale; its already-merged fix is not duplicated.
- Legacy loop APIs remain compatible while autonomy B gains a separate evidence gate.
- Scheduled reasoning and deterministic GitHub validation have separate responsibilities.
- The implementation ends with a second evidence-backed executive pass.
