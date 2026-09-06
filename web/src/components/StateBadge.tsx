import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";

const variant = { inside: "success", outside: "warning", unknown: "neutral" } as const;

export function StateBadge({ state }: { state: "inside" | "outside" | "unknown" | string }) {
  const t = useT();
  const s = (state === "inside" || state === "outside" ? state : "unknown") as keyof typeof variant;
  return <Badge variant={variant[s]}>{t(`state.${s}`)}</Badge>;
}
