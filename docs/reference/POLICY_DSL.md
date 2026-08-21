# Policy DSL Reference

The reference for the `when` / `actions` mini-language that `policies.json`
uses. Every operator, field and action listed here is validated against the
engine source (`lucidfence/core/policies.py` and `lucidfence/core/engine.py`);
anything the code does **not** support is called out as a limit rather than
promised.

When you write a policy by hand (for example to feed
[`lucidfence apply`](../operations/config_as_code.md)), this is the contract the
engine actually evaluates.

---

## How a policy is evaluated

Once per cycle, for each device, the engine:

1. Computes a **risk result** (score `0-100`, derived `severity`, and a `signals`
   bag from every registered signal provider).
2. Runs each **enabled** policy: a policy **fires** when *all* of its `when`
   conditions are true (logical **AND** — there is no `or`).
3. For every fired policy, each of its `actions` is dispatched to the UEM
   adapter (subject to dry-run / enforcement / cooldown guardrails).

Key honesty rule, straight from the code: in `RiskEngine._all_conditions`, if a
field resolves to `None` the condition is treated as **false** and the policy
does **not** fire. **Unknown never fabricates a match** — a missing signal can
only fail a condition, never satisfy one.

---

## Policy structure

`policies.json` is a **JSON list** of policy objects:

```json
[
  {
    "id": "pol-rooted-outside",
    "name": "Wipe rooted device outside its geofence",
    "description": "Rooted + outside the allowed fence: probable data exfiltration.",
    "when": [
      {"field": "fence_state", "op": "eq", "value": "outside"},
      {"field": "signal:device_health.rooted", "op": "eq", "value": true}
    ],
    "actions": [
      {"action": "notify", "params": {"channel": "ciso", "msg": "rooted outside fence"}},
      {"action": "wipe", "params": {}}
    ],
    "enabled": true,
    "severity": "critical"
  }
]
```

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `id` | string | **yes** | Unique policy id. Duplicates are rejected by `validate_policies`. |
| `name` | string | no (defaults `"policy"`) | Human label, echoed into the action log. |
| `description` | string | no | Free text. |
| `when` | list of conditions | **yes** | Non-empty list; **all** must be true (AND). |
| `actions` | list of actions | no | Dispatched when the policy fires. |
| `enabled` | bool | no (default `true`) | Disabled policies are skipped entirely. |
| `severity` | string | no (default `"medium"`) | One of `low \| medium \| high \| critical`. Metadata only — it labels the action log; it does **not** change how conditions evaluate. |

> `source` and `template_id` also exist on the `Policy` dataclass but are set by
> the Workflows module, not by hand-written policies. Leave them out.

### Condition shape

```json
{"field": "<field>", "op": "<operator>", "value": <value>}
```

- `field` is **required**.
- `op` is optional and **defaults to `gte`** if omitted (`c.get("op", "gte")`).
- `value` is **required** (`validate_policies` flags a condition with no `value`).

---

## Operators

All eight operators come from `_cmp()`. Comparison operators coerce **both**
sides with `float()`; equality operators compare the raw values as-is. Any
conversion error (e.g. `gt` on a non-numeric value) is swallowed and the
condition evaluates to **false** — it never raises.

| Operator | Meaning | Coercion | Example |
|----------|---------|----------|---------|
| `gte` | `actual >= value` | numeric (`float`) | `{"field": "risk_score", "op": "gte", "value": 70}` |
| `gt`  | `actual > value`  | numeric (`float`) | `{"field": "signal:route_state.route_deviation_m", "op": "gt", "value": 500}` |
| `lte` | `actual <= value` | numeric (`float`) | `{"field": "battery_level", "op": "lte", "value": 15}` |
| `lt`  | `actual < value`  | numeric (`float`) | `{"field": "storage_free_gb", "op": "lt", "value": 5}` |
| `eq`  | `actual == value` | none (raw) | `{"field": "fence_state", "op": "eq", "value": "outside"}` |
| `ne`  | `actual != value` | none (raw) | `{"field": "compliant", "op": "ne", "value": true}` |
| `in`  | `actual in value` (value must be a list) | none | `{"field": "platform", "op": "in", "value": ["android", "ios"]}` |
| `contains` | `value in actual` (actual treated as a string) | none | `{"field": "os_version", "op": "contains", "value": "Windows 10"}` |

Notes derived from the code:

- `in`: the **value** is the container (`actual in (value or [])`). A non-list
  value fails safely.
- `contains`: the **actual** field is the haystack (`value in (actual or "")`).
  It is a substring test on strings.
- Booleans compared with `eq`/`ne` must be JSON `true`/`false`, not `"true"`.

Any operator outside this set is rejected up front by `validate_policies`
(and by `lucidfence apply` / `validate-config`).

---

## Resolvable fields (`when[].field`)

`_resolve_field` handles a handful of names specially and falls back to a lookup
on the device record for everything else.

### Special fields

| Field | Type | Meaning |
|-------|------|---------|
| `risk_score` | number `0-100` | The composite risk score for this cycle. |
| `severity` | string | The **risk** severity derived from the score (`low<30`, `medium≥30`, `high≥55`, `critical≥80`). This is *not* the policy's own `severity` metadata. |
| `fence_state` | string | `inside` \| `outside` \| `unknown` (no location report → `unknown`). |
| `compliant` | bool / null | The device's UEM compliance flag. `null` (unknown) fails any condition. |
| `hardware_degraded` | bool | Derived: true when a hardware-health component is explicitly reported degraded. Unknown → `false`. |
| `signal:<provider>.<key>` | varies | A single key from a signal provider's output — see the next section. |

### Device fields (fallback)

Any other `field` is looked up directly on the device record (the persisted
`DeviceState`). Useful ones: `platform`, `status`, `country`, `city`,
`os_version`, `model`, `manufacturer`, `battery_level`, `storage_free_gb`,
`storage_total_gb`, `encryption_enabled`, `route_state`, `route_deviation_m`,
`risk_severity`, `department`, `assigned_user`, `supervised`, `lockdown_mode`.

A field that does not exist on the device resolves to `None` → the condition is
false. There is no error, and the policy simply does not fire on it.

---

## Posture signals (`signal:<provider>.<key>`)

Signals come from the `@register_signal` providers. Reference a single key with
`signal:<provider>.<key>`. All providers run every cycle; a provider that raises
yields an empty dict (so its keys resolve to `None` → conditions fail closed).

| Provider | Key | Type | Meaning |
|----------|-----|------|---------|
| `time_of_day` | `hour` | int / null | Local hour (0-23), `null` if unknown. |
| `time_of_day` | `off_hours` | bool | True when hour `< 7` or `>= 20`. |
| `shift_match` | `shift_known` | bool | Whether an expected shift zone is configured for the device. |
| `shift_match` | `shift_match` | bool | Whether the device's fence matches its expected shift zone. |
| `device_health` | `compliant` | bool | UEM compliance flag (coerced to bool). |
| `device_health` | `rooted` | bool | Root/jailbreak reported. |
| `device_health` | `encryption` | bool | Storage encryption on. **Unknown (`null`) is treated as `true`** — unknown posture is not evidence of disabled encryption. |
| `device_health` | `os_outdated` | bool | OS flagged outdated by the UEM. |
| `device_posture` | `disk_low` | bool | Free space `< 10%`. |
| `device_posture` | `battery_critical` | bool | Battery `<= 15%`. |
| `device_posture` | `os_unpatched` | bool | Known-old OS build heuristic (e.g. `android 12`, `ios 15`, `windows 10`). |
| `device_posture` | `encryption_off` | bool | Encryption explicitly off (unknown → **not** off). |
| `device_posture` | `lockdown_mode_off` | bool | Apple Lockdown Mode reported explicitly `false` (unknown → not penalized). |
| `device_posture` | `unsupervised` | bool | Enrollment reported explicitly unsupervised (unknown → not penalized). |
| `device_posture` | `hardware_degraded` | bool | Any hardware component explicitly degraded. |
| `device_posture` | `hardware_degraded_components` | list | Names of degraded components. |
| `device_posture` | `osquery_config_invalid` | bool | osquery config reported invalid. |
| `location_integrity` | `suspicious` | bool | Location report failed a plausibility check. |
| `location_integrity` | `checks` | list | Failed checks, e.g. `impossible_speed`, `country_flip_without_movement`, `accuracy_invalid`, `accuracy_too_perfect`. Use with `contains`. |
| `location_integrity` | `speed_kmh` | number / null | Implied speed between the last two reports. |
| `zone_risk` | `zone_risk` | number | Configured risk weight for the device's fence (`0.0` if none). |
| `route_state` | `route_state` | string | `on_route` \| `off_route` \| `unassigned`. |
| `route_state` | `route_deviation_m` | number | Meters off the assigned corridor (`0.0` if on route/unassigned). |
| `route_state` | `route_id` | string / null | Assigned route id. |

For a list-valued key like `location_integrity.checks`, use `contains`:

```json
{"field": "signal:location_integrity.checks", "op": "contains", "value": "impossible_speed"}
```

---

## Actions

An action is `{"action": "<name>", "params": { ... }}`. The catalog the
validator accepts is `VALID_POLICY_ACTIONS`
(the eight `APPLIVERY_ACTIONS` plus `retire`):

| Action | Destructive? | Notes |
|--------|:---:|-------|
| `notify` | no | Notifies an internal channel (e.g. `security`, `ciso`). **Does not touch the device.** |
| `message` | no | Pushes a message to the device. |
| `locate` | no | Forces a location report. |
| `lock` | **yes** | Remote screen lock. Cooldown-gated. |
| `reboot` | **yes** | Remote reboot. Cooldown-gated. |
| `clear_passcode` | **yes** | Removes the device passcode. Cooldown-gated. |
| `wipe` | **yes** | Remote data wipe. **Double-key** guarded (see below). |
| `retire` | **yes** | Retire/unenroll. Cooldown-gated at the policy layer; see adapter limit below. |
| `custom` | depends | Raw adapter command (`params.type` + args). |

**Destructive actions** = `{wipe, lock, clear_passcode, reboot}` in the engine
(`DESTRUCTIVE_ACTIONS`); the policy-replay layer additionally treats `retire` as
destructive. Destructive actions honor a persisted **cooldown**
(`action_cooldown_seconds`, default 3600s) so a standing violation cannot
re-issue them every cycle or after a restart.

**Double key on `wipe`.** `wipe` is the only action that never goes live without
an explicit opt-in. In enforce mode it requires `enforcement.allow_wipe: true`,
and if `enforcement.wipe_allowlist` is set it must also list the target
`device_id`. A blocked wipe is written to the audit log and does **not** arm the
cooldown. See [ENFORCEMENT.md](../operations/ENFORCEMENT.md) for the full rollout
model (`observe` → `enforce` → `allow_wipe`).

### Honesty limits on actions

- **`retire` is not in the adapter action set.** `validate_policies` accepts
  `retire`, but it is not part of the adapters' `VALID_ACTIONS`, so at execution
  most adapters return `unsupported_action`. Treat `retire` as supported at the
  *policy/replay* layer, not guaranteed at the *device* layer — check your
  UEM adapter before relying on it.
- Whether any given action actually reaches the device also depends on the
  runtime mode: in `observe`/`dry_run` nothing is issued (the log records what
  *would* have happened); in `enforce` with an `enforcement.live_actions`
  allowlist, actions not on that list run as dry-run.

---

## Complete examples

Copy-paste starting points. Each is a full `policies.json` entry.

### 1. Off-geofence AND hardware degraded → notify security

```json
{
  "id": "pol-degraded-offsite",
  "name": "Degraded hardware off-site",
  "description": "Device left its fence while a hardware component is failing.",
  "when": [
    {"field": "fence_state", "op": "eq", "value": "outside"},
    {"field": "hardware_degraded", "op": "eq", "value": true}
  ],
  "actions": [
    {"action": "notify", "params": {"channel": "security",
     "msg": "Degraded device outside its geofence"}}
  ],
  "enabled": true,
  "severity": "high"
}
```

### 2. High composite risk → lock the device

```json
{
  "id": "pol-highrisk-lock",
  "name": "Lock on high risk",
  "description": "Composite risk score at or above 70 locks the device.",
  "when": [
    {"field": "risk_score", "op": "gte", "value": 70}
  ],
  "actions": [
    {"action": "message", "params": {"text": "Your device was locked for a security review."}},
    {"action": "lock", "params": {}}
  ],
  "enabled": true,
  "severity": "critical"
}
```

### 3. Off-route by more than 500 m → alert CISO (no device action)

```json
{
  "id": "pol-route-deviation",
  "name": "Route deviation > 500 m",
  "description": "Courier left the assigned corridor by more than 500 m.",
  "when": [
    {"field": "signal:route_state.route_state", "op": "eq", "value": "off_route"},
    {"field": "signal:route_state.route_deviation_m", "op": "gt", "value": 500}
  ],
  "actions": [
    {"action": "notify", "params": {"channel": "ciso",
     "msg": "Route deviation over 500 m"}}
  ],
  "enabled": true,
  "severity": "high"
}
```

### 4. Location spoofing suspected + non-compliant → wipe (double-key)

```json
{
  "id": "pol-spoof-noncompliant",
  "name": "Impossible speed on a non-compliant device",
  "description": "Location report implies impossible movement AND device is non-compliant.",
  "when": [
    {"field": "signal:location_integrity.checks", "op": "contains", "value": "impossible_speed"},
    {"field": "compliant", "op": "eq", "value": false}
  ],
  "actions": [
    {"action": "notify", "params": {"channel": "ciso", "msg": "Possible location spoofing"}},
    {"action": "wipe", "params": {}}
  ],
  "enabled": true,
  "severity": "critical"
}
```

> Example 4's `wipe` only reaches a device when the tenant runtime is in
> `enforce` mode **and** `enforcement.allow_wipe` (and, if set, the allowlist)
> permits it. By default it is logged as a dry-run.

---

## Honesty note

- **Unknown never penalizes.** Missing posture (`null`) resolves to `None` and
  fails the condition rather than satisfying it. Encryption and Apple posture
  items (Lockdown Mode, supervision, hardware health) are only counted against a
  device when the UEM reports them *explicitly*.
- **AND only.** There is no `or` / grouping in `when`. Model an "or" as two
  separate policies.
- **Validate before you ship.** Run `lucidfence validate-config` or the dry-run
  of [`lucidfence apply`](../operations/config_as_code.md); both use the same
  `validate_policies` the engine trusts, so a config that validates there is a
  config the engine will load.
