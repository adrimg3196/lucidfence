import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const t = useT();
  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <section className="flex flex-col justify-center px-8 py-12 lg:px-16">
        <p className="text-sm font-semibold text-accent">{t("app.name")}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 max-w-[48ch] text-sm text-muted">{subtitle}</p>}
        <div className="mt-8 max-w-md">{children}</div>
      </section>
      <aside className="hidden bg-bg-2 lg:block" aria-hidden />
    </div>
  );
}
