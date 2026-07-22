/* LucidFence i18n — ES / EN
 * Non-invasive: scans visible text nodes and translates known strings.
 * Covers the dashboard shell + the strings app.js injects dynamically
 * (re-applied via MutationObserver). Data from the API (scores, CVE IDs)
 * is technical and left as-is by design.
 */
(function () {
  const ES = {
    "Command Center": "Command Center",
    "Operación": "Operación",
    "Plan": "Plan",
    "Free": "Free",
    "Ciclo": "Ciclo",
    "15 min": "15 min",
    "Estado": "Estado",
    "live": "live",
    "Geofence": "Geofence",
    "Resumen": "Resumen",
    "En vivo": "En vivo",
    "Refrescar": "Refrescar",
    "Forzar ciclo": "Forzar ciclo",
    "Comandos remotos (MDM/UEM)": "Comandos remotos (MDM/UEM)",
    "🔒 Bloquear": "🔒 Bloquear",
    "⚠️ Borrar": "⚠️ Borrar",
    "📍 Localizar": "📍 Localizar",
    "🔄 Reiniciar": "🔄 Reiniciar",
    "🔑 Reset PIN": "🔑 Reset PIN",
    "💬 Mensaje": "💬 Mensaje",
    "Apps instaladas · CVE": "Apps instaladas · CVE",
    "Actividad reciente": "Actividad reciente",
    "Accede a LucidFence": "Accede a LucidFence",
    "Gestiona tu flota de forma segura": "Gestiona tu flota de forma segura",
    "Entrar": "Entrar",
    "Crear cuenta": "Crear cuenta",
    "Email": "Email",
    "Organización": "Organización",
    "Contraseña": "Contraseña",
    "Cerrar sesión": "Cerrar sesión",
    "Mapa de flota": "Mapa de flota",
    "Inventario de Flota": "Inventario de Flota",
    "Motor de Riesgo": "Motor de Riesgo",
    "IA de Flota": "IA de Flota",
    "Incidentes": "Incidentes",
    "Geovallas": "Geovallas",
    "Rutas": "Rutas",
    "SOAR·CVE": "SOAR·CVE",
    "Dispositivos": "Dispositivos",
    "Riesgo": "Riesgo",
    "Mapa": "Mapa",
    "Inventario": "Inventario",
    "IA · MoA": "IA · MoA",
    "Eventos": "Eventos",
    "Acciones": "Acciones",
    "Alertas": "Alertas",
    "Objetivos": "Objetivos",
    "Ajustes": "Ajustes",
    "Resumen de operación": "Resumen de operación",
    "Pregunta a la IA sobre tu flota": "Pregunta a la IA sobre tu flota",
    "Mapa de flota en vivo": "Mapa de flota en vivo",
    "Conformidad": "Conformidad",
    "Resumen ejecutivo": "Resumen ejecutivo",
    "En geovalla": "En geovalla",
    "Fuera de geovalla": "Fuera de geovalla",
    "Estado geovalla": "Estado geovalla",
    "Cobertura de geovalla": "Cobertura de geovalla",
    "Conformidad de flota": "Conformidad de flota",
    "Dispositivos por nivel de riesgo": "Dispositivos por nivel de riesgo",
    "Dispositivos en riesgo alto": "Dispositivos en riesgo alto",
    "dispositivos en riesgo alto": "dispositivos en riesgo alto",
    "Buscar dispositivo": "Buscar dispositivo",
    "No hay datos de flota": "No hay datos de flota",
    "No hay dispositivo": "No hay dispositivo",
    "Abrir detalle": "Abrir detalle",
    "Crea tu organización": "Crea tu organización",
    "Crea tu primera alert": "Crea tu primera alert",
    "Cola operativa de incidente": "Cola operativa de incidente",
    "CVE alto": "CVE alto",
    "CVE crítico": "CVE crítico",
    "Inventario CVE por dispositivo": "Inventario CVE por dispositivo",
    "Mensaje para el dispositivo": "Mensaje para el dispositivo",
    "Eliminar esta geovalla": "Eliminar esta geovalla",
    "Construye contexto de flota": "Construye contexto de flota",
    "El score de riesgo": "El score de riesgo",
    "El detalle": "El detalle",
    "Este dispositivo": "Este dispositivo",
    "este dispositivo": "este dispositivo",
    "Gestiona tu flota": "Gestiona tu flota",
    "la IA sobre tu flota": "la IA sobre tu flota",
    "Las rutas agrupan geovalla": "Las rutas agrupan geovalla",
    "No se pudieron cargar detalle": "No se pudieron cargar detalle",
    "acciones reales sobre los dispositivo": "acciones reales sobre los dispositivo",
    "aparecen aquí cuando un dispositivo": "aparecen aquí cuando un dispositivo",
    "aparecerá aquí conforme la flota": "aparecerá aquí conforme la flota",
    "estado actual de la flota": "estado actual de la flota",
    "están fuera de su geovalla": "están fuera de su geovalla",
    "estos datos de la flota": "estos datos de la flota",
    "evita acceso sin sesión": "evita acceso sin sesión",
    "fuera de geovalla": "fuera de geovalla",
    "httpOnly y no exponemos contraseña": "httpOnly y no exponemos contraseña",
    "lista de dispositivo": "lista de dispositivo",
    "modelo con contexto de flota": "modelo con contexto de flota",
    "hallazgos del motor de riesgo": "hallazgos del motor de riesgo",
    "Email y contraseña": "Email y contraseña",
    "El nombre de la organización": "El nombre de la organización",
    "Inteligencia de flota": "Inteligencia de flota",
    "Riesgo de cruce": "Riesgo de cruce",
    "Anomalías GPS": "Anomalías GPS",
    "Evidencia local": "Evidencia local",
    "Compañía autónoma": "Compañía autónoma",
    "Compañía autónoma de geofencing": "Compañía autónoma de geofencing",
    "Nuevo objetivo medible": "Nuevo objetivo medible",
    "Ejecutar ciclo seguro": "Ejecutar ciclo seguro",
    "Pausar compañía": "Pausar compañía",
    "Reanudar compañía": "Reanudar compañía",
    "Squad disponible": "Squad disponible",
    "Cola gobernada": "Cola gobernada",
    "Contrato de autonomía": "Contrato de autonomía",
    "Objetivos activos": "Objetivos activos",
    "Tareas abiertas": "Tareas abiertas",
    "Cobertura de evidencia": "Cobertura de evidencia",
    "Bloqueos de seguridad": "Bloqueos de seguridad",
    "Crear objetivo": "Crear objetivo",
    "Nivel de autonomía": "Nivel de autonomía",
    "Objetivo: reducir salidas no autorizadas": "Objetivo: reducir salidas no autorizadas",
    "Resultado operativo esperado": "Resultado operativo esperado",
    "Field Intelligence": "Inteligencia de Campo",
    "Geo Policy": "Política Geo",
    "UEM Operations": "Operaciones UEM",
    "Risk & Compliance": "Riesgo y Compliance",
    "Product Value": "Valor de Producto",
    "Independent Critic": "Crítica Independiente"
  };
  const EN = {
    "Command Center": "Command Center",
    "Operación": "Operations",
    "Plan": "Plan",
    "Free": "Free",
    "Ciclo": "Cycle",
    "15 min": "15 min",
    "Estado": "Status",
    "live": "live",
    "Geofence": "Geofence",
    "Resumen": "Overview",
    "En vivo": "Live",
    "Refrescar": "Refresh",
    "Forzar ciclo": "Force cycle",
    "Comandos remotos (MDM/UEM)": "Remote commands (MDM/UEM)",
    "🔒 Bloquear": "🔒 Lock",
    "⚠️ Borrar": "⚠️ Wipe",
    "📍 Localizar": "📍 Locate",
    "🔄 Reiniciar": "🔄 Reboot",
    "🔑 Reset PIN": "🔑 Reset PIN",
    "💬 Mensaje": "💬 Message",
    "Apps instaladas · CVE": "Installed apps · CVE",
    "Actividad reciente": "Recent activity",
    "Accede a LucidFence": "Sign in to LucidFence",
    "Gestiona tu flota de forma segura": "Manage your fleet securely",
    "Entrar": "Sign in",
    "Crear cuenta": "Create account",
    "Email": "Email",
    "Organización": "Organization",
    "Contraseña": "Password",
    "Cerrar sesión": "Sign out",
    "Mapa de flota": "Fleet map",
    "Inventario de Flota": "Fleet inventory",
    "Motor de Riesgo": "Risk Engine",
    "IA de Flota": "Fleet AI",
    "Incidentes": "Incidents",
    "Geovallas": "Geofences",
    "Rutas": "Routes",
    "SOAR·CVE": "SOAR·CVE",
    "Dispositivos": "Devices",
    "Riesgo": "Risk",
    "Mapa": "Map",
    "Inventario": "Inventory",
    "IA · MoA": "Fleet AI · MoA",
    "Eventos": "Events",
    "Acciones": "Actions",
    "Alertas": "Alerts",
    "Objetivos": "Goals",
    "Ajustes": "Settings",
    "Resumen de operación": "Operations summary",
    "Pregunta a la IA sobre tu flota": "Ask the fleet AI",
    "Mapa de flota en vivo": "Live fleet map",
    "Conformidad": "Compliance",
    "Recent activity": "Recent activity",
    "En geovalla": "Inside geofence",
    "Fuera de geovalla": "Outside geofence",
    "Estado geovalla": "Geofence status",
    "Cobertura de geovalla": "Geofence coverage",
    "Conformidad de flota": "Fleet compliance",
    "Dispositivos por nivel de riesgo": "Devices by risk level",
    "Dispositivos en riesgo alto": "High-risk devices",
    "dispositivos en riesgo alto": "high-risk devices",
    "Buscar dispositivo": "Search device",
    "No hay datos de flota": "No fleet data",
    "No hay dispositivo": "No device",
    "Abrir detalle": "Open detail",
    "Crea tu organización": "Create your organization",
    "Crea tu primera alert": "Create your first alert",
    "Cola operativa de incidente": "Incident ops queue",
    "CVE alto": "High CVE",
    "CVE crítico": "Critical CVE",
    "Inventario CVE por dispositivo": "CVE inventory by device",
    "Mensaje para el dispositivo": "Message to device",
    "Eliminar esta geovalla": "Delete this geofence",
    "Construye contexto de flota": "Builds fleet context",
    "El score de riesgo": "The risk score",
    "El detalle": "The detail",
    "Este dispositivo": "This device",
    "este dispositivo": "this device",
    "Gestiona tu flota": "Manage your fleet",
    "la IA sobre tu flota": "the AI on your fleet",
    "Las rutas agrupan geovalla": "Routes group geofences",
    "No se pudieron cargar detalle": "Could not load detail",
    "acciones reales sobre los dispositivo": "real actions on devices",
    "aparecen aquí cuando un dispositivo": "appear here when a device",
    "aparecerá aquí conforme la flota": "will appear as the fleet",
    "estado actual de la flota": "current fleet status",
    "están fuera de su geovalla": "are outside their geofence",
    "estos datos de la flota": "this fleet data",
    "evita acceso sin sesión": "prevents access without session",
    "fuera de geovalla": "outside geofence",
    "httpOnly y no exponemos contraseña": "httpOnly and we never expose passwords",
    "lista de dispositivo": "device list",
    "modelo con contexto de flota": "model with fleet context",
    "hallazgos del motor de riesgo": "risk engine findings",
    "Email y contraseña": "Email and password",
    "El nombre de la organización": "The organization name",
    "Inteligencia de flota": "Fleet intelligence",
    "Riesgo de cruce": "Crossing risk",
    "Anomalías GPS": "GPS anomalies",
    "Evidencia local": "Local evidence",
    "Compañía autónoma": "Autonomous company",
    "Compañía autónoma de geofencing": "Autonomous geofencing company",
    "Nuevo objetivo medible": "New measurable goal",
    "Ejecutar ciclo seguro": "Run safe cycle",
    "Pausar compañía": "Pause company",
    "Reanudar compañía": "Resume company",
    "Squad disponible": "Available squad",
    "Cola gobernada": "Governed queue",
    "Contrato de autonomía": "Autonomy contract",
    "Objetivos activos": "Active goals",
    "Tareas abiertas": "Open tasks",
    "Cobertura de evidencia": "Evidence coverage",
    "Bloqueos de seguridad": "Safety blocks",
    "Crear objetivo": "Create goal",
    "Nivel de autonomía": "Autonomy level",
    "Objetivo: reducir salidas no autorizadas": "Goal: reduce unauthorized exits",
    "Resultado operativo esperado": "Expected operational outcome",
    "Field Intelligence": "Field Intelligence",
    "Geo Policy": "Geo Policy",
    "UEM Operations": "UEM Operations",
    "Risk & Compliance": "Risk & Compliance",
    "Product Value": "Product Value",
    "Independent Critic": "Independent Critic"
  };

  // Build a bidirectional lookup from the two parallel maps ES (keys) / EN (values).
  const LOOKUP = {};
  for (const k in ES) {
    LOOKUP[k] = { es: k, en: EN[k] };           // ES text -> pair
    if (EN[k]) LOOKUP[EN[k]] = { es: k, en: EN[k] }; // EN text -> pair
  }

  function translateValue(value, lang) {
    const trimmed = String(value || "").trim();
    if (LOOKUP[trimmed]) return String(value).replace(trimmed, LOOKUP[trimmed][lang]);
    let output = String(value || "");
    const phrases = Object.keys(LOOKUP).filter(k => k.length >= 8).sort((a,b) => b.length-a.length);
    for (const phrase of phrases) {
      if (output.includes(phrase)) output = output.split(phrase).join(LOOKUP[phrase][lang]);
    }
    return output;
  }

  function applyI18n(lang) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) {
      if (!n.nodeValue || !n.nodeValue.trim()) continue;
      if (n.parentNode && (n.parentNode.tagName === "SCRIPT" || n.parentNode.tagName === "STYLE")) continue;
      nodes.push(n);
    }
    for (const node of nodes) {
      node.nodeValue = translateValue(node.nodeValue, lang);
    }
    for (const el of document.querySelectorAll("[placeholder],[title],[aria-label]")) {
      for (const attr of ["placeholder", "title", "aria-label"]) {
        if (el.hasAttribute(attr)) el.setAttribute(attr, translateValue(el.getAttribute(attr), lang));
      }
    }
  }

  function setLang(lang) {
    try { localStorage.setItem("lf_lang", lang); } catch (e) {}
    applyI18n(lang);
    document.documentElement.lang = lang;
  }

  function initI18n() {
    let lang = "es";
    try { lang = localStorage.getItem("lf_lang") || "es"; } catch (e) {}
    applyI18n(lang);
    document.documentElement.lang = lang;
    // i18n.js owns its own language button (floating), so app.js topbar
    // handlers can't interfere with it.
    const btn = document.createElement("button");
    btn.id = "lfLangBtn";
    btn.textContent = lang === "en" ? "ES" : "EN";
    btn.setAttribute("style", "position:fixed;right:12px;bottom:12px;z-index:9999;" +
      "background:var(--accent);color:#fff;border:0;border-radius:8px;" +
      "padding:8px 14px;font:600 12px var(--font);cursor:pointer;box-shadow:var(--shadow)");
    btn.setAttribute("aria-label", lang === "en" ? "Cambiar a español" : "Switch to English");
    btn.addEventListener("click", function () {
      const cur = document.documentElement.lang || "es";
      setLang(cur === "en" ? "es" : "en");
      btn.textContent = (document.documentElement.lang === "en") ? "ES" : "EN";
      btn.setAttribute("aria-label", document.documentElement.lang === "en" ? "Cambiar a español" : "Switch to English");
    });
    document.body.appendChild(btn);
    // Re-apply when app.js injects dynamic content.
    if (window.MutationObserver) {
      let scheduled = false;
      const mo = new MutationObserver(function () {
        if (scheduled) return;
        scheduled = true;
        setTimeout(function () {
          scheduled = false;
          let l = "es";
          try { l = localStorage.getItem("lf_lang") || "es"; } catch (e) {}
          applyI18n(l);
        }, 150);
      });
      mo.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initI18n);
  } else {
    initI18n();
  }
  window.setLang = setLang;
})();
