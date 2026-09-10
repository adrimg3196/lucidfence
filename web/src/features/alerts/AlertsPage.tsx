import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useAlerts, useCreateAlert, useDeleteAlert, useEvaluateAlerts, useMe, useUpdateAlert, type AlertRule } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { slugify } from "@/lib/slug";
import { alertKindKeys, alertKinds, alertUnitKeys, emptyAlertForm, fromRule, makeAlertFormSchema, severityValues, toRule, type AlertFormValues } from "./alertForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function AlertsPage() {
  const t = useT();
  const alerts = useAlerts();
  const create = useCreateAlert();
  const update = useUpdateAlert();
  const remove = useDeleteAlert();
  const evaluate = useEvaluateAlerts();
  const me = useMe();
  const canWrite = can(me.data?.capabilities, "alert:write");
  const [editing, setEditing] = useState<AlertRule | null>(null);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<AlertRule | null>(null);
  const schema = useMemo(() => makeAlertFormSchema(t), [t]);
  const form = useForm<z.input<typeof schema>, unknown, AlertFormValues>({ resolver: zodResolver(schema), defaultValues: emptyAlertForm });
  const kind = form.watch("kind") as AlertRule["kind"];
  const name = form.watch("name") as string;
  useEffect(() => {
    if (!editing) form.setValue("id", slugify(name), { shouldValidate: false });
  }, [name, editing, form]);
  const startNew = () => {
    setEditing(null);
    form.reset(emptyAlertForm);
    setOpen(true);
  };
  const startEdit = (r: AlertRule) => {
    setEditing(r);
    form.reset(fromRule(r));
    setOpen(true);
  };
  const submit = form.handleSubmit(async (values) => {
    await (editing ? update.mutateAsync(toRule(values)) : create.mutateAsync(toRule(values)));
    setOpen(false);
    setEditing(null);
  });
  const errs = form.formState.errors;
  const mutationError = create.error ?? update.error;
  const firings = evaluate.data?.firings ?? [];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t("alerts.title")}</h1>
        {canWrite && (
          <div className="flex gap-2">
            <Button variant="secondary" disabled={evaluate.isPending} onClick={() => evaluate.mutate()}>
              {t("alerts.preview")}
            </Button>
            <Button onClick={startNew}>
              <Plus size={16} aria-hidden /> {t("alerts.new")}
            </Button>
          </div>
        )}
      </div>
      {open && canWrite && (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? t("alerts.edit") : t("alerts.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="name">{t("alert.name")}</Label>
                <Input id="name" aria-invalid={!!errs.name} {...form.register("name")} />
                <FieldError message={errs.name?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="id">{t("alert.id")}</Label>
                <Input id="id" readOnly={!!editing} aria-invalid={!!errs.id} {...form.register("id")} />
                <FieldError message={errs.id?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="kind">{t("alert.kind")}</Label>
                <NativeSelect id="kind" {...form.register("kind")}>
                  {alertKinds.map((k) => (
                    <option key={k} value={k}>
                      {t(alertKindKeys[k])}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="threshold">{`${t("alert.threshold")} (${t(alertUnitKeys[kind])})`}</Label>
                <Input id="threshold" type="number" step="any" disabled={kind === "noncompliant"} aria-invalid={!!errs.threshold} {...form.register("threshold")} />
                <FieldError message={errs.threshold?.message} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="severity">{t("alert.severity")}</Label>
                <NativeSelect id="severity" {...form.register("severity")}>
                  {severityValues.map((s) => (
                    <option key={s} value={s}>
                      {t(`severity.${s}` as never)}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="flex items-center gap-2 self-end">
                <input id="enabled" type="checkbox" className="h-4 w-4 accent-accent" {...form.register("enabled")} />
                <Label htmlFor="enabled">{t("alert.enabled")}</Label>
              </div>
              {mutationError && (
                <div className="sm:col-span-2">
                  <ErrorState error={mutationError} />
                </div>
              )}
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" disabled={create.isPending || update.isPending}>
                  {t("alert.save")}
                </Button>
                <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                  {t("alert.cancel")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
      {alerts.isPending && <Loading rows={4} />}
      {alerts.error && <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />}
      {alerts.data && alerts.data.items.length === 0 && <Empty title={t("alerts.empty")} />}
      {alerts.data && alerts.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("alerts.col.name")}</TH>
              <TH>{t("alerts.col.kind")}</TH>
              <TH>{t("alerts.col.threshold")}</TH>
              <TH>{t("alerts.col.severity")}</TH>
              <TH>{t("alerts.col.enabled")}</TH>
              <TH />
            </tr>
          </THead>
          <TBody>
            {alerts.data.items.map((r) => (
              <TR key={r.id}>
                <TD className="font-medium">{r.name}</TD>
                <TD>{t(alertKindKeys[r.kind])}</TD>
                <TD className="tabular-nums">{r.kind === "noncompliant" ? "-" : `${r.threshold} ${t(alertUnitKeys[r.kind])}`}</TD>
                <TD>
                  <SeverityBadge severity={r.severity} />
                </TD>
                <TD>{t(r.enabled ? "common.yes" : "common.no")}</TD>
                <TD className="text-right">
                  {canWrite && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => startEdit(r)}>
                        {t("alerts.edit")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setPending(r)}>
                        {t("alerts.delete")}
                      </Button>
                    </>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {evaluate.error && <ErrorState error={evaluate.error} />}
      {evaluate.data && (
        <section aria-label={t("alerts.preview")} className="space-y-2">
          <h2 className="text-sm font-semibold">{t("alerts.preview")}</h2>
          <p className="text-sm text-muted">{t("alerts.preview.help")}</p>
          <p className="text-sm text-fg-2">{t("alerts.preview.count", { count: evaluate.data.count, devices: evaluate.data.devices })}</p>
          {firings.length === 0 ? (
            <Empty title={t("alerts.preview.empty")} />
          ) : (
            <Table>
              <THead>
                <tr>
                  <TH>{t("alerts.preview.col.rule")}</TH>
                  <TH>{t("alerts.preview.col.device")}</TH>
                  <TH>{t("alerts.preview.col.reason")}</TH>
                </tr>
              </THead>
              <TBody>
                {firings.map((f) => (
                  <TR key={`${f.rule_id}-${f.device_id}`}>
                    <TD>{f.rule_name}</TD>
                    <TD>{f.device_name}</TD>
                    <TD className="text-muted">{f.reason}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </section>
      )}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={t("alerts.delete")}
        description={pending ? t("alerts.delete.confirm", { name: pending.name }) : undefined}
        confirmLabel={t("alerts.delete")}
        cancelLabel={t("alert.cancel")}
        confirmDisabled={remove.isPending}
        onConfirm={() => pending && remove.mutate(pending.id, { onSuccess: () => setPending(null) })}
      >
        {remove.error && <ErrorState error={remove.error} />}
      </ConfirmDialog>
    </div>
  );
}
