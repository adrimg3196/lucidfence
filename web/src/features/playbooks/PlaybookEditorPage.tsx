import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router";
import { FormProvider, useForm, type Control, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Warning } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { ConditionRows } from "@/features/policies/ConditionRows";
import { ActionRows } from "@/features/policies/ActionRows";
import type { PolicyFormValues } from "@/features/policies/policyForm";
import { useCreatePlaybook, usePlaybooks, usePolicyFields, useUpdatePlaybook } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { slugify } from "@/lib/slug";
import { destructiveIn, emptyPlaybookForm, fromPlaybook, makePlaybookFormSchema, toPlaybook, type PlaybookFormValues } from "./playbookForm";

const severities = ["low", "medium", "high", "critical"] as const;

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function PlaybookEditorPage() {
  const { id } = useParams();
  const editing = !!id;
  const t = useT();
  const navigate = useNavigate();
  // No hay hook de playbook suelto (T22 no expone usePlaybook): la lista ya
  // está cacheada por TanStack Query y el editor busca en ella.
  const playbooks = usePlaybooks();
  const catalog = usePolicyFields();
  const create = useCreatePlaybook();
  const update = useUpdatePlaybook();
  const schema = useMemo(() => makePlaybookFormSchema(t), [t]);
  const form = useForm<PlaybookFormValues>({ resolver: zodResolver(schema), defaultValues: emptyPlaybookForm });
  const existing = playbooks.data?.items.find((p) => p.id === id);
  useEffect(() => {
    if (existing) form.reset(fromPlaybook(existing));
  }, [existing, form]);
  const name = form.watch("name");
  useEffect(() => {
    if (!editing) form.setValue("id", slugify(name), { shouldValidate: false });
  }, [name, editing, form]);
  const submit = form.handleSubmit(async (values) => {
    const now = new Date().toISOString();
    const playbook = toPlaybook(values, now);
    await (editing ? update.mutateAsync(playbook) : create.mutateAsync(playbook));
    navigate("/playbooks");
  });
  if (editing && playbooks.isPending) return <Loading rows={6} />;
  if (playbooks.error) return <ErrorState error={playbooks.error} onRetry={() => playbooks.refetch()} />;
  const errs = form.formState.errors;
  const mutationError = create.error ?? update.error;
  // Las filas de acciones son las de T23; la acción vive en su clave `action`
  // (es lo que declara PolicyAction y lo que ActionRows edita).
  const gated = destructiveIn(form.watch("actions") as unknown as { action?: string }[]);
  // ConditionRows/ActionRows están tipadas contra PolicyFormValues; el
  // formulario de playbook comparte esas dos claves exactas, así que la
  // conversión se hace una sola vez y aquí.
  const control = form.control as unknown as Control<PolicyFormValues>;
  // ActionRows lee `register` de useFormContext (T23: features/policies/ActionRows.tsx),
  // así que necesita el mismo FormProvider que PolicyEditorPage, no solo `control`.
  return (
    <FormProvider {...(form as unknown as UseFormReturn<PolicyFormValues>)}>
      <form onSubmit={submit} noValidate className="max-w-3xl space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">{editing ? t("playbook.editor.edit") : t("playbook.editor.new")}</h1>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="name">{t("playbook.name")}</Label>
            <Input id="name" aria-invalid={!!errs.name} {...form.register("name")} />
            <FieldError message={errs.name?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="id">{t("playbook.id")}</Label>
            <Input id="id" aria-invalid={!!errs.id} readOnly={editing} {...form.register("id")} />
            <FieldError message={errs.id?.message} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="description">{t("playbook.description")}</Label>
            <Input id="description" {...form.register("description")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="severity">{t("playbook.severity")}</Label>
            <NativeSelect id="severity" {...form.register("severity")}>
              {severities.map((s) => (
                <option key={s} value={s}>
                  {t(`severity.${s}`)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex items-center gap-2 pt-6">
            <input id="enabled" type="checkbox" className="size-4" {...form.register("enabled")} />
            <Label htmlFor="enabled">{t("playbook.enabled")}</Label>
          </div>
        </div>
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-fg-2">{t("playbook.when")}</legend>
          {/* Ruling M2-R10: ConditionRows/ActionRows son las de T23, no las del
              esqueleto de este brief — una condición es campo *y* operador, y
              ActionRows toma su `control` sin `fields`. */}
          <ConditionRows control={control} fields={catalog.data?.fields ?? []} ops={catalog.data?.ops ?? []} />
          <FieldError message={errs.when?.message} />
        </fieldset>
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-fg-2">{t("playbook.actions")}</legend>
          <ActionRows control={control} />
          <FieldError message={errs.actions?.message} />
        </fieldset>
        {gated.length > 0 && (
          <div className="flex items-start gap-3 rounded-[var(--radius-ui)] border border-sev-medium/30 bg-sev-medium/5 p-4">
            <Warning size={20} className="mt-0.5 shrink-0 text-sev-medium" aria-hidden />
            <div>
              <p className="text-sm font-medium">{t("playbook.destructive.title")}</p>
              <p className="mt-0.5 text-sm text-fg-2">
                {t("playbook.destructive.help", { actions: gated.map((a) => t(`fence.action.${a}` as never)).join(", ") })}
              </p>
            </div>
          </div>
        )}
        {mutationError && <ErrorState error={mutationError} />}
        <div className="flex gap-2">
          <Button type="submit" disabled={create.isPending || update.isPending}>
            {t("playbook.save")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate("/playbooks")}>
            {t("playbook.cancel")}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}
