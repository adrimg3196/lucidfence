import { Play } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useEngineStatus, useRunOnce, useMe } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";

export function EngineCard() {
  const t = useT();
  const { lang } = useLang();
  const status = useEngineStatus();
  const run = useRunOnce();
  const me = useMe();
  const canRun = can(me.data?.capabilities, "engine:run");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("overview.engine")}</CardTitle>
        {canRun && (
          <Button size="sm" variant="secondary" onClick={() => run.mutate()} disabled={run.isPending}>
            <Play size={14} aria-hidden />
            {run.isPending ? t("overview.engine.running") : t("overview.engine.run")}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {run.error && <ErrorState error={run.error} />}
        {status.isPending && <Loading rows={3} />}
        {status.error && <ErrorState error={status.error} onRetry={() => status.refetch()} />}
        {status.data && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <dt className="text-muted">{t("overview.engine.mode")}</dt>
            <dd>{status.data.mode}</dd>
            <dt className="text-muted">{t("overview.engine.enforcement")}</dt>
            <dd>
              <Badge variant="info">{status.data.enforcement}</Badge>
            </dd>
            <dt className="text-muted">{t("overview.engine.interval")}</dt>
            <dd>{Math.round(status.data.interval_seconds / 60)} min</dd>
            <dt className="text-muted">{t("overview.engine.cycles")}</dt>
            <dd>{status.data.cycles}</dd>
            <dt className="text-muted">{t("overview.engine.lastCycle")}</dt>
            <dd>{formatDateTime(status.data.last_cycle?.at, lang)}</dd>
            {status.data.last_error && (
              <>
                <dt className="text-muted">{t("overview.engine.lastError")}</dt>
                <dd className="text-sev-high">{status.data.last_error}</dd>
              </>
            )}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
