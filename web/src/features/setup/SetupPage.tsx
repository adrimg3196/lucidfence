import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/states/ErrorState";
import { useSetup } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const schema = z.object({
  email: z.email(),
  name: z.string().trim().min(1),
  password: z.string().min(10),
  mode: z.enum(["demo", "empty"]),
});
type Form = z.infer<typeof schema>;

export function SetupPage() {
  const t = useT();
  const navigate = useNavigate();
  const setup = useSetup();
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { email: "", name: "", password: "", mode: "demo" } });
  const errors = form.formState.errors;
  const onSubmit = form.handleSubmit(async (values) => {
    await setup.mutateAsync(values);
    navigate("/", { replace: true });
  });
  return (
    <AuthLayout title={t("setup.title")} subtitle={t("setup.subtitle")}>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <Field label={t("setup.email")} id="email" error={errors.email && "email"}>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...form.register("email")} />
        </Field>
        <Field label={t("setup.name")} id="name" error={errors.name && "name"}>
          <Input id="name" autoComplete="name" aria-invalid={!!errors.name} {...form.register("name")} />
        </Field>
        <Field label={t("setup.password")} id="password" error={errors.password && "password"}>
          <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
        </Field>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-fg-2">{t("setup.mode")}</legend>
          {(["demo", "empty"] as const).map((m) => (
            <label key={m} className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-ui)] border border-border p-3 has-[:checked]:border-accent has-[:checked]:bg-accent/5">
              <input type="radio" value={m} aria-label={t(`setup.mode.${m}`)} className="mt-1" {...form.register("mode")} />
              <span>
                <span className="block text-sm font-medium">{t(`setup.mode.${m}`)}</span>
                <span className="block text-sm text-muted">{t(`setup.mode.${m}.help`)}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {setup.error && <ErrorState error={setup.error} />}
        <Button type="submit" size="lg" className="w-full" disabled={setup.isPending}>
          {t("setup.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}

export function Field({ label, id, error, children }: { label: string; id: string; error?: string | false; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && (
        <p role="alert" className="text-xs text-sev-high">
          {label}
        </p>
      )}
    </div>
  );
}
