export function formatDateTime(iso: string | null | undefined, lang: string): string {
  if (!iso) return "—".replace("—", "-");
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return new Intl.DateTimeFormat(lang, { dateStyle: "short", timeStyle: "short" }).format(d);
}

export function percent(part: number, total: number): string {
  if (total === 0) return "0 %";
  return `${Math.round((part / total) * 100)} %`;
}

export function meters(m: number | null | undefined): string {
  if (m == null) return "-";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}
