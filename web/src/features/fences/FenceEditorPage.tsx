import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useCreateFence, useFence, useUpdateFence } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { slugify } from "@/lib/slug";
import { actionValues, whenValues, emptyForm, makeFenceFormSchema, fromFence, toFence, type FenceForm } from "./fenceForm";

// M1-R12: el backend rechaza el id reservado "none"; el slug autogenerado
// desde el nombre nunca debe producirlo (la edición manual del id sigue
// validándose en el servidor y su error se muestra vía ErrorState).
function slugAvoidingReserved(name: string): string {
  const slug = slugify(name);
  return slug === "none" ? `${slug}-1` : slug;
}

// Fix round 1 (M1-R25 punto 5): mensaje inline bajo un campo con aria-invalid,
// reutilizado por todos los campos del formulario.
function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function FenceEditorPage() {
  const { id } = useParams();
  const editing = !!id;
  const t = useT();
  const navigate = useNavigate();
  const existing = useFence(id ?? "");
  const create = useCreateFence();
  const update = useUpdateFence();
  // M1-R27 (C15): fenceFormSchema depende de `t` (sus mensajes ya no están
  // fijos en español), así que se reconstruye con useMemo en vez de
  // importarse como un const.
  const fenceFormSchema = useMemo(() => makeFenceFormSchema(t), [t]);
  // centerLat/centerLng/radiusM usan z.coerce, así que el tipo de entrada del
  // formulario difiere del tipo validado (FenceForm); se lo indicamos a
  // useForm con los tres genéricos para que zodResolver tipe correctamente.
  const form = useForm<z.input<typeof fenceFormSchema>, unknown, FenceForm>({ resolver: zodResolver(fenceFormSchema), defaultValues: emptyForm });
  const actions = useFieldArray({ control: form.control, name: "actions" });
  const kind = form.watch("kind");
  const name = form.watch("name");
  useEffect(() => {
    if (!editing) form.setValue("id", slugAvoidingReserved(name), { shouldValidate: false });
  }, [name, editing, form]);
  useEffect(() => {
    if (existing.data) form.reset(fromFence(existing.data));
  }, [existing.data, form]);
  const submit = form.handleSubmit(async (values) => {
    const fence = toFence(values);
    await (editing ? update.mutateAsync(fence) : create.mutateAsync(fence));
    navigate("/fences");
  });
  if (editing && existing.isPending) return <Loading rows={6} />;
  if (editing && existing.error) return <ErrorState error={existing.error} />;
  const errs = form.formState.errors;
  const mutationError = create.error ?? update.error;
  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{editing ? t("fence.editor.edit") : t("fence.editor.new")}</h1>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="name">{t("fence.name")}</Label>
          <Input id="name" aria-invalid={!!errs.name} {...form.register("name")} />
          <FieldError message={errs.name?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="id">{t("fence.id")}</Label>
          <Input id="id" aria-invalid={!!errs.id} readOnly={editing} {...form.register("id")} />
          <FieldError message={errs.id?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="kind">{t("fence.kind")}</Label>
          <NativeSelect id="kind" aria-invalid={!!errs.kind} {...form.register("kind")}>
            <option value="circle">{t("fence.kind.circle")}</option>
            <option value="polygon">{t("fence.kind.polygon")}</option>
          </NativeSelect>
          <FieldError message={errs.kind?.message} />
        </div>
      </div>
      {kind === "circle" ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="centerLat">{t("fence.lat")}</Label>
            <Input id="centerLat" type="number" step="any" aria-invalid={!!errs.centerLat} {...form.register("centerLat")} />
            <FieldError message={errs.centerLat?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="centerLng">{t("fence.lng")}</Label>
            <Input id="centerLng" type="number" step="any" aria-invalid={!!errs.centerLng} {...form.register("centerLng")} />
            <FieldError message={errs.centerLng?.message} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="radiusM">{t("fence.radius")}</Label>
            <Input id="radiusM" type="number" step="1" aria-invalid={!!errs.radiusM} {...form.register("radiusM")} />
            <FieldError message={errs.radiusM?.message} />
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="polygonText">{t("fence.polygon")}</Label>
          <textarea id="polygonText" rows={6} aria-invalid={!!errs.polygonText} className="w-full rounded-[var(--radius-ui)] border border-border bg-panel p-3 font-mono text-sm" {...form.register("polygonText")} />
          {errs.polygonText && <p role="alert" className="text-xs text-sev-high">{t("fence.error.polygon")}</p>}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="violationIntervalCycles">{t("fence.rules.violationInterval")}</Label>
          <Input id="violationIntervalCycles" type="number" step="1" min="0" aria-invalid={!!errs.violationIntervalCycles} {...form.register("violationIntervalCycles")} />
          <FieldError message={errs.violationIntervalCycles?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="dwellSeconds">{t("fence.rules.dwell")}</Label>
          <Input id="dwellSeconds" type="number" step="1" min="0" aria-invalid={!!errs.dwellSeconds} {...form.register("dwellSeconds")} />
          <FieldError message={errs.dwellSeconds?.message} />
        </div>
      </div>
      {/* M1-R27: el motor todavía no aplica estas reglas (C3 diferido a M2). */}
      <p className="text-sm text-muted">{t("fence.rules.help")}</p>
      <fieldset className="space-y-3">
        <div className="flex items-center justify-between">
          <legend className="text-sm font-medium text-fg-2">{t("fence.actions")}</legend>
          <Button type="button" variant="secondary" size="sm" onClick={() => actions.append({ action: "message", when: "on_enter", text: "", enabled: true })}>
            {t("fence.actions.add")}
          </Button>
        </div>
        {actions.fields.map((field, i) => (
          <div key={field.id} className="grid items-end gap-3 rounded-[var(--radius-ui)] border border-border p-3 sm:grid-cols-[1fr_1fr_2fr_auto]">
            <div className="space-y-1.5">
              <Label htmlFor={`action-${i}`}>{t("fences.col.actions")}</Label>
              <NativeSelect id={`action-${i}`} {...form.register(`actions.${i}.action`)}>
                {actionValues.map((a) => (
                  <option key={a} value={a}>
                    {t(`fence.action.${a}`)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`when-${i}`}>{t("fence.when")}</Label>
              <NativeSelect id={`when-${i}`} {...form.register(`actions.${i}.when`)}>
                {whenValues.map((w) => (
                  <option key={w} value={w}>
                    {t(`fence.when.${w}`)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`text-${i}`}>{t("fence.action.text")}</Label>
              <Input id={`text-${i}`} {...form.register(`actions.${i}.text`)} />
            </div>
            <Button type="button" variant="ghost" size="icon" aria-label={t("fences.delete")} onClick={() => actions.remove(i)}>
              <Trash size={16} aria-hidden />
            </Button>
          </div>
        ))}
      </fieldset>
      {mutationError && <ErrorState error={mutationError} />}
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending || update.isPending}>
          {t("fence.save")}
        </Button>
        <Button type="button" variant="secondary" onClick={() => navigate("/fences")}>
          {t("fence.cancel")}
        </Button>
      </div>
    </form>
  );
}
