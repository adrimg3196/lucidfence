# NOVA Product Discovery Learnings & Architecture Directives

## Mission
Log critical learnings and architectural guardrails discovered during the product discovery phase for visionary features destined for implementation by Hermes.

## Key Learnings & Guardrails

1. **Local-First & Zero Telemetry Paramountcy**:
   - Every visionary feature (P2P mesh, predictive SOAR, quantum-safe ledger, air-gap store & forward, policy synthesizer) must operate entirely on the tenant's local environment.
   - External network calls are strictly restricted to configured egress allowlists via `internal/notify`.

2. **Single Binary & Strict Physical Limits**:
   - LucidFence 2.0 compiles into a single Go binary with embedded web assets (`internal/web`).
   - File size limits (<= 400 lines Go, <= 300 lines TSX), function limits (<= 60 lines, <= 40 statements, cyclomatic complexity <= 15) and dependency allowlists (`internal/arch/allowlist_go.txt`) must be strictly honored during Hermes implementation.

3. **Additive Runtime Battery Checks (`internal/battery`)**:
   - Every claim or feature introduced in the product MUST add corresponding runtime battery checks to maintain the `RUNTIME: N/N` assertion.

4. **Hermes Implementation Strategy**:
   - Features in `EXPLORE` horizon (`docs/roadmap/PRODUCT_ROADMAP.md`) are specification-ready and modularized to map directly into Go domain packages under `internal/domain/`.
