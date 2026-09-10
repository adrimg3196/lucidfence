import { useMemo } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { Trash } from "@phosphor-icons/react";
import { api, unwrap } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/states/ErrorState";
import { keys, useInvalidate, type Settings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { fromRisk, makeRiskSchema, toRisk, type RiskFormValues, type RiskSettings } from "./settingsForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

// M2-C3: PUT /api/v1/settings/risk ya está en el contrato y en schema.d.ts
// (T21) pero T22 no le dio un hook propio en hooks.m2.ts (solo lo hizo para
// enforcement/webhook/egress) y esa puerta de hooks queda fuera del alcance
// de esta tarea. Mismo patrón que useUpdateEnforcement/useUpdateEgress,
// local a este fichero: api/unwrap (@/api/client) y keys/useInvalidate
// (reexportados por @/api/hooks) ya son superficie pública.
function useUpdateRisk() {
  const invalidate = useInvalidate(keys.settings, keys.engine);
  return useMutation({
    mutationFn: async (body: RiskSettings) => unwrap(await api.PUT("/api/v1/settings/risk", { body })),
    onSuccess: invalidate,
  });
}

export function RiskForm({ settings }: { settings: Settings }) {
  const t = useT();
  const update = useUpdateRisk();
  const schema = useMemo(() => makeRiskSchema(t), [t]);
  const form = useForm<z.input<typeof schema>, unknown, RiskFormValues>({
    resolver: zodResolver(schema),
    defaultValues: fromRisk(settings.risk),
  });
  const shiftZones = useFieldArray({ control: form.control, name: "shiftZones" });
  const zoneRisk = useFieldArray({ control: form.control, name: "zoneRisk" });
  const errs = form.formState.errors;

  const submit = form.handleSubmit(async (values) => {
    await update.mutateAsync(toRisk(values));
  });

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg-2">{t("settings.risk.offHours")}</legend>
        <p className="text-xs text-muted">{t("settings.risk.offHours.help")}</p>
        <div className="flex items-end gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="offHoursStart">{t("settings.risk.offHoursStart")}</Label>
            <Input
              id="offHoursStart"
              type="number"
              step="1"
              min="0"
              max="23"
              aria-invalid={!!errs.offHoursStart}
              {...form.register("offHoursStart")}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="offHoursEnd">{t("settings.risk.offHoursEnd")}</Label>
            <Input id="offHoursEnd" type="number" step="1" min="0" max="23" aria-invalid={!!errs.offHoursEnd} {...form.register("offHoursEnd")} />
          </div>
        </div>
        <FieldError message={errs.offHoursStart?.message ?? errs.offHoursEnd?.message} />
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg-2">{t("settings.risk.shiftZones")}</legend>
        <p className="text-xs text-muted">{t("settings.risk.shiftZones.help")}</p>
        {shiftZones.fields.map((f, i) => (
          <div key={f.id} className="flex items-center gap-2">
            <Input aria-label={t("settings.risk.deviceId")} {...form.register(`shiftZones.${i}.deviceId`)} />
            <Input aria-label={t("settings.risk.fenceId")} {...form.register(`shiftZones.${i}.fenceId`)} />
            <FieldError message={errs.shiftZones?.[i]?.deviceId?.message ?? errs.shiftZones?.[i]?.fenceId?.message} />
            <Button type="button" variant="ghost" size="icon" aria-label={t("fences.delete")} onClick={() => shiftZones.remove(i)}>
              <Trash size={16} aria-hidden />
            </Button>
          </div>
        ))}
        <Button type="button" variant="secondary" size="sm" onClick={() => shiftZones.append({ deviceId: "", fenceId: "" })}>
          {t("settings.add")}
        </Button>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg-2">{t("settings.risk.zoneRisk")}</legend>
        <p className="text-xs text-muted">{t("settings.risk.zoneRisk.help")}</p>
        {zoneRisk.fields.map((f, i) => (
          <div key={f.id} className="flex items-center gap-2">
            <Input aria-label={t("settings.risk.fenceId")} {...form.register(`zoneRisk.${i}.fenceId`)} />
            <Input
              aria-label={t("settings.risk.weight")}
              type="number"
              step="0.1"
              min="0"
              max="1"
              {...form.register(`zoneRisk.${i}.weight`)}
            />
            <FieldError message={errs.zoneRisk?.[i]?.fenceId?.message ?? errs.zoneRisk?.[i]?.weight?.message} />
            <Button type="button" variant="ghost" size="icon" aria-label={t("fences.delete")} onClick={() => zoneRisk.remove(i)}>
              <Trash size={16} aria-hidden />
            </Button>
          </div>
        ))}
        <Button type="button" variant="secondary" size="sm" onClick={() => zoneRisk.append({ fenceId: "", weight: 0 })}>
          {t("settings.add")}
        </Button>
      </fieldset>

      {update.error && <ErrorState error={update.error} />}
      <Button type="submit" disabled={update.isPending}>
        {t("fence.save")}
      </Button>
    </form>
  );
}
