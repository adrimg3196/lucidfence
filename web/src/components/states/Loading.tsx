import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";

export function Loading({ rows = 4, label }: { rows?: number; label?: string }) {
  const t = useT();
  return (
    <div role="status" aria-label={label ?? t("state.loading")} className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
