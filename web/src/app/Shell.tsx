import { NavLink, Outlet } from "react-router";
import { Moon, Sun, SignOut, Translate } from "@phosphor-icons/react";
import { navItems } from "./nav";
import { useTheme } from "./theme";
import { useT, useLang } from "@/lib/i18n";
import { useMe, useLogout } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Shell() {
  const t = useT();
  const { lang, setLang } = useLang();
  const { theme, toggle } = useTheme();
  const me = useMe();
  const logout = useLogout();
  const user = me.data?.user;
  return (
    <div className="grid min-h-dvh grid-cols-1 md:grid-cols-[232px_1fr]">
      <aside className="border-b border-border bg-panel md:border-b-0 md:border-r">
        <div className="flex h-16 items-center px-5 text-base font-semibold tracking-tight">{t("app.name")}</div>
        <nav aria-label="principal" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {navItems.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn("flex items-center gap-2.5 rounded-[var(--radius-ui)] px-3 py-2 text-sm text-fg-2 hover:bg-bg-2 hover:text-fg", isActive && "bg-accent/10 text-accent")
              }
            >
              <Icon size={18} weight="regular" aria-hidden />
              {t(key)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-panel px-6">
          <span className="text-sm text-muted">{user?.org}</span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" aria-label={t("lang.toggle")} onClick={() => setLang(lang === "es" ? "en" : "es")}>
              <Translate size={18} aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" aria-label={t("theme.toggle")} onClick={toggle}>
              {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
            </Button>
            {user && <span className="ml-2 text-sm font-medium">{user.name}</span>}
            <Button variant="ghost" size="icon" aria-label={t("nav.logout")} onClick={() => logout.mutate()} disabled={logout.isPending}>
              <SignOut size={18} aria-hidden />
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
