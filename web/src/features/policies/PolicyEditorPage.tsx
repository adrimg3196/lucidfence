import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useCreatePolicy, usePolicy, usePolicyFields, useUpdatePolicy } from "@/api/hooks";
import { useT, type Key } from "@/lib/i18n";
import { slugify } from "@/lib/slug";
import { ActionRows } from "./ActionRows";
import { ConditionRows } from "./ConditionRows";
import { TemplatesDialog } from "./TemplatesDialog";
import { WhatIfPanel } from "./WhatIfPanel";
import { emptyPolicyForm, fromPolicy, isDestructive, makePolicyFormSchema, severityValues, simulationKey, toPolicy, type PolicyFormValues } from "./policyForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function PolicyEditorPage() {
  const { id } = useParams();
  const editing = !!id;
  const t = useT();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const existing = usePolicy(id ?? "");
  const catalog = usePolicyFields();
  const create = useCreatePolicy();
  const update = useUpdatePolicy();
  const schema = useMemo(() => makePolicyFormSchema(t), [t]);
  const form = useForm<PolicyFormValues>({ resolver: zodResolver(schema), defaultValues: emptyPolicyForm });
  const [templatesOpen, setTemplatesOpen] = useState(search.get("plantillas") === "1");
  // La puerta del what-if: haber simulado ESTA política, no el veredicto de
  // la simulación. Se guarda la firma de lo simulado, no un booleano: con un
  // booleano, simular algo inocuo y volver destructiva la acción después
  // dejaba guardar un wipe que nadie había mirado.
  const [simulatedKey, setSimulatedKey] = useState<string | null>(null);
  const values = form.watch();
  const name = values.name;

  useEffect(() => {
    // El id solo se autogenera en una política nueva que no venga de una
    // plantilla: la plantilla trae el suyo y es el que la ata a su origen.
    if (!editing && !form.getValues("templateId")) form.setValue("id", slugify(name), { shouldValidate: false });
  }, [name, editing, form]);
  useEffect(() => {
    if (existing.data) form.reset(fromPolicy(existing.data));
  }, [existing.data, form]);

  const submit = form.handleSubmit(async (v) => {
    const policy = toPolicy(v, new Date().toISOString());
    await (editing ? update.mutateAsync(policy) : create.mutateAsync(policy));
    navigate("/policies");
  });

  if (editing && existing.isPending) return <Loading rows={6} />;
  if (editing && existing.error) return <ErrorState error={existing.error} onRetry={() => existing.refetch()} />;

  const errs = form.formState.errors;
  const mutationError = create.error ?? update.error;
  const candidate = toPolicy(values, existing.data?.created_at ?? new Date().toISOString());
  const destructive = candidate.actions.some((a) => isDestructive(a.action));
  const blocked = destructive && simulatedKey !== simulationKey(candidate);
  return (
    <FormProvider {...form}>
      <form onSubmit={submit} noValidate className="max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">{editing ? t("policy.editor.edit") : t("policy.editor.new")}</h1>
          {!editing && (
            <Button type="button" variant="secondary" onClick={() => setTemplatesOpen(true)}>
              <Sparkle size={16} aria-hidden /> {t("policy.templates")}
            </Button>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="name">{t("policy.name")}</Label>
            <Input id="name" aria-invalid={!!errs.name} {...form.register("name")} />
            <FieldError message={errs.name?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="id">{t("policy.id")}</Label>
            <Input id="id" aria-invalid={!!errs.id} readOnly={editing} {...form.register("id")} />
            <FieldError message={errs.id?.message} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="description">{t("policy.description")}</Label>
            <Input id="description" {...form.register("description")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="severity">{t("policy.severity")}</Label>
            <NativeSelect id="severity" {...form.register("severity")}>
              {severityValues.map((s) => (
                <option key={s} value={s}>
                  {t(`policy.severity.${s}` as Key)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex items-end gap-2">
            <input id="enabled" type="checkbox" className="size-4" {...form.register("enabled")} />
            <Label htmlFor="enabled">{t("policy.enabled")}</Label>
          </div>
        </div>
        {catalog.error && <ErrorState error={catalog.error} onRetry={() => catalog.refetch()} />}
        <ConditionRows control={form.control} fields={catalog.data?.fields ?? []} ops={catalog.data?.ops ?? []} />
        <FieldError message={errs.when?.message} />
        <ActionRows control={form.control} />
        {/* Ruling M2-R11: `actions` pasa a exigir al menos una acción, así que
            lleva el mismo hueco de error que `when` en vez de fallar en
            silencio contra el 400 del servidor. */}
        <FieldError message={errs.actions?.message} />
        <WhatIfPanel policy={candidate} onRun={(p) => setSimulatedKey(simulationKey(p))} />
        {blocked && <p className="text-sm text-sev-high">{t("policy.whatif.gate")}</p>}
        {mutationError && <ErrorState error={mutationError} />}
        <div className="flex gap-2">
          <Button type="submit" disabled={blocked || create.isPending || update.isPending}>
            {t("policy.save")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate("/policies")}>
            {t("policy.cancel")}
          </Button>
        </div>
        <TemplatesDialog
          open={templatesOpen}
          onOpenChange={setTemplatesOpen}
          onPick={(p) => {
            form.reset(fromPolicy(p));
            // No hace falta invalidar nada a mano: la plantilla trae otras
            // condiciones y otras acciones, así que la firma deja de casar.
            setTemplatesOpen(false);
          }}
        />
      </form>
    </FormProvider>
  );
}
