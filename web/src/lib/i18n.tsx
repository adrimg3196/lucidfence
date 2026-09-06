import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export const es = {
  "app.name": "LucidFence",
  "nav.overview": "Visión general",
  "nav.map": "Mapa",
  "nav.devices": "Dispositivos",
  "nav.fences": "Geocercas",
  "nav.logout": "Cerrar sesión",
  "theme.toggle": "Cambiar tema",
  "lang.toggle": "English",
  "state.loading": "Cargando",
  "state.empty": "Nada que mostrar",
  "state.error": "Algo ha fallado",
  "state.retry": "Reintentar",
  "setup.title": "Configura LucidFence",
  "setup.subtitle": "Crea la cuenta de propietario. Todo se guarda en esta máquina.",
  "setup.email": "Email",
  "setup.name": "Nombre",
  "setup.password": "Contraseña (mínimo 10 caracteres)",
  "setup.mode": "Cómo quieres empezar",
  "setup.mode.demo": "Demo local con flota simulada",
  "setup.mode.demo.help": "Seis dispositivos en Madrid, dos geocercas y una ruta. Sin conectar ningún UEM.",
  "setup.mode.empty": "Vacío, conectaré mi UEM",
  "setup.mode.empty.help": "Sin datos. Los conectores reales llegan en el siguiente hito.",
  "setup.submit": "Crear cuenta y entrar",
  "login.title": "Iniciar sesión",
  "login.email": "Email",
  "login.password": "Contraseña",
  "login.submit": "Entrar",
  "login.invalid": "Email o contraseña incorrectos",
  "login.throttled": "Demasiados intentos. Espera un minuto.",
  "overview.title": "Visión general",
  "overview.devices": "Dispositivos",
  "overview.inside": "Dentro",
  "overview.outside": "Fuera",
  "overview.unknown": "Sin ubicación",
  "overview.compliance": "Cumplimiento",
  "overview.engine": "Motor",
  "overview.engine.mode": "Modo",
  "overview.engine.enforcement": "Enforcement",
  "overview.engine.interval": "Intervalo",
  "overview.engine.lastCycle": "Último ciclo",
  "overview.engine.cycles": "Ciclos",
  "overview.engine.lastError": "Último error",
  "overview.engine.run": "Ejecutar ciclo ahora",
  "overview.engine.running": "Ejecutando",
  "overview.events": "Últimas transiciones",
  "overview.providers": "Proveedores",
  "overview.noEvents": "Aún no hay transiciones. Ejecuta un ciclo.",
  "map.title": "Mapa en vivo",
  "map.legend.inside": "Dentro de geocerca",
  "map.legend.outside": "Fuera",
  "map.legend.unknown": "Sin ubicación",
  "map.disabled": "El mapa está desactivado en la configuración (map.enabled=false).",
  "devices.title": "Dispositivos",
  "devices.search": "Buscar por nombre, usuario, modelo o serie",
  "devices.filter.all": "Todos",
  "devices.col.name": "Nombre",
  "devices.col.platform": "Plataforma",
  "devices.col.state": "Geocerca",
  "devices.col.user": "Usuario",
  "devices.col.lastReport": "Último informe",
  "devices.empty": "Sin dispositivos. Ejecuta un ciclo del motor.",
  "device.inventory": "Inventario",
  "device.risk": "Riesgo",
  "device.risk.pending": "Sin evaluar: el motor de riesgo llega en el siguiente hito.",
  "device.trail": "Recorrido",
  "device.trail.empty": "Sin recorrido registrado todavía",
  "device.events": "Transiciones",
  "device.events.empty": "Sin transiciones de este dispositivo",
  "device.back": "Volver a dispositivos",
  "device.field.os": "Sistema",
  "device.field.model": "Modelo",
  "device.field.serial": "Serie",
  "device.field.battery": "Batería",
  "device.field.storage": "Almacenamiento",
  "device.field.encryption": "Cifrado",
  "device.field.user": "Usuario",
  "device.field.department": "Departamento",
  "device.field.route": "Ruta",
  "fences.title": "Geocercas",
  "fences.new": "Nueva geocerca",
  "fences.col.name": "Nombre",
  "fences.col.kind": "Tipo",
  "fences.col.actions": "Acciones",
  "fences.empty": "Sin geocercas. Crea la primera.",
  "fences.delete": "Eliminar",
  "fences.delete.confirm": "¿Eliminar la geocerca {name}?",
  "fence.editor.new": "Nueva geocerca",
  "fence.editor.edit": "Editar geocerca",
  "fence.name": "Nombre",
  "fence.id": "Identificador",
  "fence.kind": "Forma",
  "fence.kind.circle": "Círculo",
  "fence.kind.polygon": "Polígono",
  "fence.center": "Centro (lat, lng)",
  "fence.radius": "Radio (m)",
  "fence.polygon": "Vértices, uno por línea: lat, lng",
  "fence.actions": "Acciones por evento",
  "fence.actions.add": "Añadir acción",
  "fence.when.on_enter": "Al entrar",
  "fence.when.on_exit": "Al salir",
  "fence.when.on_violation": "Violación sostenida",
  "fence.when.on_unknown": "Al perder ubicación",
  "fence.save": "Guardar",
  "fence.cancel": "Cancelar",
  "fence.error.polygon": "Un polígono necesita al menos 3 vértices válidos",
  "state.inside": "dentro",
  "state.outside": "fuera",
  "state.unknown": "sin ubicación",
  "common.yes": "Sí",
  "common.no": "No",
  "common.unknown": "Desconocido",
} as const;

export type Key = keyof typeof es;
export type Lang = "es" | "en";

export const en: Record<Key, string> = {
  "app.name": "LucidFence",
  "nav.overview": "Overview",
  "nav.map": "Map",
  "nav.devices": "Devices",
  "nav.fences": "Geofences",
  "nav.logout": "Sign out",
  "theme.toggle": "Toggle theme",
  "lang.toggle": "Español",
  "state.loading": "Loading",
  "state.empty": "Nothing to show",
  "state.error": "Something went wrong",
  "state.retry": "Retry",
  "setup.title": "Set up LucidFence",
  "setup.subtitle": "Create the owner account. Everything stays on this machine.",
  "setup.email": "Email",
  "setup.name": "Name",
  "setup.password": "Password (10 characters minimum)",
  "setup.mode": "How do you want to start",
  "setup.mode.demo": "Local demo with a simulated fleet",
  "setup.mode.demo.help": "Six devices in Madrid, two geofences and one route. No UEM connected.",
  "setup.mode.empty": "Empty, I will connect my UEM",
  "setup.mode.empty.help": "No data. Real connectors arrive in the next milestone.",
  "setup.submit": "Create account and sign in",
  "login.title": "Sign in",
  "login.email": "Email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.invalid": "Wrong email or password",
  "login.throttled": "Too many attempts. Wait a minute.",
  "overview.title": "Overview",
  "overview.devices": "Devices",
  "overview.inside": "Inside",
  "overview.outside": "Outside",
  "overview.unknown": "No location",
  "overview.compliance": "Compliance",
  "overview.engine": "Engine",
  "overview.engine.mode": "Mode",
  "overview.engine.enforcement": "Enforcement",
  "overview.engine.interval": "Interval",
  "overview.engine.lastCycle": "Last cycle",
  "overview.engine.cycles": "Cycles",
  "overview.engine.lastError": "Last error",
  "overview.engine.run": "Run a cycle now",
  "overview.engine.running": "Running",
  "overview.events": "Latest transitions",
  "overview.providers": "Providers",
  "overview.noEvents": "No transitions yet. Run a cycle.",
  "map.title": "Live map",
  "map.legend.inside": "Inside a geofence",
  "map.legend.outside": "Outside",
  "map.legend.unknown": "No location",
  "map.disabled": "The map is disabled in the configuration (map.enabled=false).",
  "devices.title": "Devices",
  "devices.search": "Search by name, user, model or serial",
  "devices.filter.all": "All",
  "devices.col.name": "Name",
  "devices.col.platform": "Platform",
  "devices.col.state": "Geofence",
  "devices.col.user": "User",
  "devices.col.lastReport": "Last report",
  "devices.empty": "No devices. Run an engine cycle.",
  "device.inventory": "Inventory",
  "device.risk": "Risk",
  "device.risk.pending": "Not evaluated: the risk engine arrives in the next milestone.",
  "device.trail": "Trail",
  "device.trail.empty": "No trail recorded yet",
  "device.events": "Transitions",
  "device.events.empty": "No transitions for this device",
  "device.back": "Back to devices",
  "device.field.os": "OS",
  "device.field.model": "Model",
  "device.field.serial": "Serial",
  "device.field.battery": "Battery",
  "device.field.storage": "Storage",
  "device.field.encryption": "Encryption",
  "device.field.user": "User",
  "device.field.department": "Department",
  "device.field.route": "Route",
  "fences.title": "Geofences",
  "fences.new": "New geofence",
  "fences.col.name": "Name",
  "fences.col.kind": "Kind",
  "fences.col.actions": "Actions",
  "fences.empty": "No geofences. Create the first one.",
  "fences.delete": "Delete",
  "fences.delete.confirm": "Delete geofence {name}?",
  "fence.editor.new": "New geofence",
  "fence.editor.edit": "Edit geofence",
  "fence.name": "Name",
  "fence.id": "Identifier",
  "fence.kind": "Shape",
  "fence.kind.circle": "Circle",
  "fence.kind.polygon": "Polygon",
  "fence.center": "Center (lat, lng)",
  "fence.radius": "Radius (m)",
  "fence.polygon": "Vertices, one per line: lat, lng",
  "fence.actions": "Actions per event",
  "fence.actions.add": "Add action",
  "fence.when.on_enter": "On enter",
  "fence.when.on_exit": "On exit",
  "fence.when.on_violation": "Standing violation",
  "fence.when.on_unknown": "On lost location",
  "fence.save": "Save",
  "fence.cancel": "Cancel",
  "fence.error.polygon": "A polygon needs at least 3 valid vertices",
  "state.inside": "inside",
  "state.outside": "outside",
  "state.unknown": "no location",
  "common.yes": "Yes",
  "common.no": "No",
  "common.unknown": "Unknown",
};

const dicts: Record<Lang, Record<Key, string>> = { es, en };

// M1-R20: español por defecto, sin autodetección del navegador
// (constraints.md: la UI arranca en español; el inglés solo llega vía el
// toggle. navigator.language no se consulta nunca).
export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem("lf.lang");
    if (saved === "es" || saved === "en") return saved;
  } catch {
    /* sin storage */
  }
  return "es";
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Record<string, string | number>) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? detectLang());
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("lf.lang", l);
    } catch {
      /* sin storage */
    }
  }, []);
  const t = useCallback(
    (key: Key, vars?: Record<string, string | number>) => {
      let s: string = dicts[lang][key] ?? key;
      for (const [k, v] of Object.entries(vars ?? {})) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useT fuera de I18nProvider");
  return ctx;
}

export function useT() {
  return useI18n().t;
}

export function useLang() {
  const { lang, setLang } = useI18n();
  return { lang, setLang };
}
