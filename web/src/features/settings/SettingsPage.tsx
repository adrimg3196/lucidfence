import { useState } from "react";
import { Navigate } from "react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useMe, useSettings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { EgressForm } from "./EgressForm";
import { EnforcementForm } from "./EnforcementForm";
import { RiskForm } from "./RiskForm";
import { WebhooksForm } from "./WebhooksForm";

// Settings es un documento único con valores por defecto (settings.Default,
// T7): no tiene estado "vacío". Los tres estados que sí aplican son
// cargando, error y contenido; el redirect por falta de engine:config es el
// "no hay nada que ver aquí" propio de esta vista.
export function SettingsPage() {
  const t = useT();
  const me = useMe();
  const settings = useSettings();
  const [tab, setTab] = useState("enforcement");

  if (!me.isPending && !can(me.data?.capabilities, "engine:config")) return <Navigate to="/" replace />;
  if (me.isPending || settings.isPending) return <Loading rows={6} />;
  if (settings.error) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  const s = settings.data!;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("settings.title")}</h1>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="enforcement">{t("settings.tab.enforcement")}</TabsTrigger>
          <TabsTrigger value="webhooks">{t("settings.tab.webhooks")}</TabsTrigger>
          <TabsTrigger value="egress">{t("settings.tab.egress")}</TabsTrigger>
          <TabsTrigger value="risk">{t("settings.tab.risk")}</TabsTrigger>
        </TabsList>
        <TabsContent value="enforcement" className="pt-4">
          <EnforcementForm settings={s} />
        </TabsContent>
        <TabsContent value="webhooks" className="pt-4">
          <WebhooksForm settings={s} />
        </TabsContent>
        <TabsContent value="egress" className="pt-4">
          <EgressForm settings={s} />
        </TabsContent>
        <TabsContent value="risk" className="pt-4">
          <RiskForm settings={s} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
