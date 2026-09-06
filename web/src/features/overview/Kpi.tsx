export function Kpi({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "success" | "warning" | "danger" }) {
  const color = { neutral: "text-fg", success: "text-sev-low", warning: "text-sev-medium", danger: "text-sev-high" }[tone];
  return (
    <div className="rounded-[var(--radius-ui)] border border-border bg-panel px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-3xl font-semibold tabular-nums tracking-tight ${color}`}>{value}</p>
    </div>
  );
}
