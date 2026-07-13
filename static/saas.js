/* LucidFence SaaS — client core: auth, router, API helpers, shell. */
(function () {
  "use strict";
  const _HTTP_METHODS = new Set(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]);
  const API = (a, b, c, headers) => {
    let method = "GET", path, body;
    if (_HTTP_METHODS.has(String(a).toUpperCase()) && b !== undefined) {
      // forma: API(method, path, body)
      method = String(a).toUpperCase();
      path = b;
      body = c;
    } else {
      // forma: API(path, opts)
      path = a;
      const opts = b || {};
      method = String(opts.method || "GET").toUpperCase();
      body = opts.body;
      if (opts.headers) headers = Object.assign({}, headers, opts.headers);
    }
    const init = {
      method,
      credentials: "same-origin",
      headers: Object.assign({ "Content-Type": "application/json" }, headers || {}),
    };
    if (body !== undefined && body !== null) init.body = JSON.stringify(body);
    return fetch(path, init)
      .then(r => r.json()
        .then(d => Object.assign({ ok: r.ok, status: r.status }, d))
        .catch(() => ({ ok: r.ok, status: r.status, error: "invalid_json", _raw: true })));
  };

  const state = {
    user: null, org: null, plan: null, role: null,
    mode: "simulation", dryRun: true,
    view: "overview", map: null,
  };

  // ---- Reicon design system (real paths from github.com/dqev/reicon) ----
  const NAV_ICONS = { overview: "grid", map: "map", devices: "devices", routes: "route",
    workflows: "bolt", risk: "shield-alert", policies: "shield-check", compliance: "chart",
    billing: "tag", users: "users", settings: "settings" };
  const LABEL_ICONS = [
    [/forzar ciclo|actualizar|refrescar/i, "refresh"], [/salir|cerrar sesi/i, "power-off"],
    [/nueva|crear|invitar|activar|a\u00f1adir/i, "plus"], [/guardar/i, "check-circle"],
    [/probar|ver en mapa|visualizar/i, "eye"], [/export|descargar/i, "download"],
    [/desactivar|eliminar|borrar/i, "trash"], [/bloquear|lock/i, "lock-keyhole"],
    [/ruta/i, "route"], [/workflow/i, "bolt"], [/incidente|riesgo|alerta/i, "shield-alert"],
    [/geovalla|mapa|ubicaci/i, "map"], [/dispositivo|flota/i, "devices"],
    [/usuario|miembro/i, "users"], [/pol\u00edtica|conformidad|seguridad/i, "shield-check"],
    [/ajuste|credencial|configuraci/i, "settings"], [/plan|facturaci/i, "tag"]
  ];
  const iconNameFor = text => {
    const t = String(text || "").trim();
    const hit = LABEL_ICONS.find(([rx]) => rx.test(t));
    return hit ? hit[1] : "info-circle";
  };
  const iconSpan = (name, size, cls) => {
    const span = document.createElement("span");
    span.className = cls || "ui-icon";
    span.setAttribute("aria-hidden", "true");
    span.innerHTML = window.reicon ? reicon(name, { size: size || 18 }) : "";
    return span;
  };
  function decorateIcons(scope) {
    if (!window.reicon) return;
    const base = scope && scope.querySelectorAll ? scope : document;
    base.querySelectorAll("#nav a:not([data-reicon-ready])").forEach(a => {
      a.prepend(iconSpan(NAV_ICONS[a.dataset.view] || "circle-info", 19));
      a.dataset.reiconReady = "1";
    });
    base.querySelectorAll("button:not([data-reicon-ready])").forEach(b => {
      if (b.closest(".switch-tab") || b.classList.contains("chip")) return;
      b.prepend(iconSpan(iconNameFor(b.textContent), 16));
      b.dataset.reiconReady = "1";
    });
    base.querySelectorAll(".card .hd h3:not([data-reicon-ready])").forEach(h3 => {
      h3.prepend(iconSpan(iconNameFor(h3.textContent), 16, "section-icon"));
      h3.style.display = "inline-flex";
      h3.style.alignItems = "center";
      h3.style.gap = "7px";
      h3.dataset.reiconReady = "1";
    });
    base.querySelectorAll(".brand .logo:not([data-reicon-ready])").forEach(logo => {
      logo.textContent = "";
      logo.append(iconSpan("shield-check", 21));
      logo.dataset.reiconReady = "1";
    });
  }
  window.GFIcons = { decorate: decorateIcons, icon: (n, o) => reicon(n, o || {}) };

  // ---- toasts ----
  function toast(msg, kind) {
    const t = document.createElement("div");
    t.className = "toast " + (kind || "");
    t.innerHTML = "<b>" + (kind === "ok" ? "Listo" : kind === "bad" ? "Error" : "Info") + "</b><small>" + msg + "</small>";
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 3800);
  }

  // ---- auth flow ----
  let selectedPlan = "pro";
  function showAuth() {
    document.getElementById("authScreen").classList.remove("hidden");
    document.getElementById("appShell").classList.add("hidden");
  }
  function showApp() {
    document.getElementById("authScreen").classList.add("hidden");
    document.getElementById("appShell").classList.remove("hidden");
  }

  function bindAuth() {
    const tabLogin = document.getElementById("tabLogin");
    const tabSignup = document.getElementById("tabSignup");
    const signupFields = document.getElementById("signupFields");
    const planField = document.getElementById("planField");
    const submit = document.getElementById("authSubmit");
    let mode = "login";
    function setMode(m) {
      mode = m;
      tabLogin.classList.toggle("active", m === "login");
      tabSignup.classList.toggle("active", m === "signup");
      signupFields.classList.toggle("hidden", m !== "signup");
      planField.classList.toggle("hidden", m !== "signup");
      submit.textContent = m === "login" ? "Iniciar sesión" : "Crear cuenta";
    }
    tabLogin.onclick = () => setMode("login");
    tabSignup.onclick = () => setMode("signup");
    document.querySelectorAll(".plan").forEach(p => p.onclick = () => {
      document.querySelectorAll(".plan").forEach(x => x.classList.remove("active"));
      p.classList.add("active"); selectedPlan = p.dataset.plan;
    });
    submit.onclick = async (e) => {
      e.preventDefault();
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const err = document.getElementById("authError");
      err.style.display = "none";
      if (!email || !password) { err.textContent = "Email y contraseña requeridos"; err.style.display = "block"; return; }
      let res;
      if (mode === "login") res = await API("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      else {
        const name = document.getElementById("name").value.trim();
        const orgName = document.getElementById("orgName").value.trim();
        if (!name || !orgName) { err.textContent = "Nombre y organización requeridos"; err.style.display = "block"; return; }
        res = await API("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name, org_name: orgName, plan: selectedPlan }) });
      }
      if (res.error) { err.textContent = res.error; err.style.display = "block"; return; }
      await bootstrap();
    };
    document.getElementById("logoutBtn").onclick = async () => {
      await API("/api/auth/logout", { method: "POST" });
      state.user = null; showAuth();
    };
  }

  async function bootstrap() {
    let me = await API("/api/auth/me");
    if (!me.user) {
      // Auto-login con la cuenta demo (producto 100% local: sin fricción de login).
      await API("/api/auth/login", { method: "POST",
        body: JSON.stringify({ email: "ciso@acme.test", password: "[REDACTED]" }) });
      me = await API("/api/auth/me");
    }
    if (!me.user) { showAuth(); return; }
    state.user = me.user;
    const org = await API("/api/org");
    if (org.org) {
      state.org = org.org.id; state.plan = org.plan; state.role = org.role;
      document.getElementById("orgName").textContent = org.org.name;
      document.getElementById("orgPlan").textContent = "plan: " + (org.plan ? org.plan.label : org.org.plan);
    }
    const st = await API("/api/settings/status");
    state.mode = st.mode || "simulation"; state.dryRun = st.dry_run;
    renderModeBadge();
    showApp();
    bindNav();
    decorateIcons(document);
    bindCycle();
    const initial = (location.hash || "").replace("#", "");
    const valid = ["overview","map","devices","routes","workflows","risk","policies","compliance","billing","users","settings"];
    goView(valid.includes(initial) ? initial : "overview");
    window.addEventListener("hashchange", () => {
      const v = (location.hash || "").replace("#", "");
      if (valid.includes(v)) goView(v);
    });
  }

  function renderModeBadge() {
    const b = document.getElementById("modeBadge");
    if (state.dryRun) { b.className = "badge dry"; b.innerHTML = '<span class="dot"></span>dry-run (simulación)'; }
    else { b.className = "badge live"; b.innerHTML = '<span class="dot"></span>live · Applivery'; }
  }

  function bindNav() {
    document.querySelectorAll("#nav a").forEach(a => a.onclick = () => { location.hash = a.dataset.view; });
  }
  function bindCycle() {
    document.getElementById("cycleBtn").onclick = async () => {
      const r = await API("/api/run-once", { method: "POST" });
      if (r.ok) toast("Ciclo ejecutado", "ok"); else toast(r.error || "sin permiso", "bad");
      goView(state.view, true);
    };
  }

  async function goView(view, refresh) {
    state.view = view;
    document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.view === view));
    const titles = { overview: ["Resumen de flota", "Monitorización geoespacial en tiempo real"],
      map: ["Mapa en vivo", "Posiciones y geovallas"], devices: ["Dispositivos", "Flota gestionada"],
      routes: ["Rutas", "Adherencia del comercial a su ruta asignada"],
      workflows: ["Workflows integrados", "Lógica lista para Applivery: plantillas y creación fácil"],
      risk: ["Risk Center", "Dispositivos de mayor riesgo"], policies: ["Políticas", "Parámetros y reglas UEM"],
      compliance: ["Conformidad", "Cumplimiento de flota"], billing: ["Facturación", "Plan y límites (mock)"],
      users: ["Usuarios", "Miembros de la organización"], settings: ["Ajustes", "Credenciales y modo"] };
    const t = titles[view] || ["", ""];
    document.getElementById("viewTitle").textContent = t[0];
    document.getElementById("viewSub").textContent = t[1];
    document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
    document.getElementById("view-" + view).classList.remove("hidden");
    if (window.GFViews && GFViews[view]) {
      try {
        await GFViews[view](document.getElementById("view-" + view), state, API, toast);
        decorateIcons(document.getElementById("view-" + view));
      } catch (err) {
        console.error("view error:", err);
        const root = document.getElementById("view-" + view);
        if (root) root.innerHTML = '<div class="card"><div class="bd"><p style="color:var(--error)">'
          + 'No se pudo cargar esta vista: ' + (err && err.message ? err.message : err)
          + '</p></div></div>';
        toast("Error al cargar la vista " + view, "bad");
      }
    }
  }

  window.GF = { state, API, toast, goView };
  // Views such as Workflows populate asynchronously after their renderer returns.
  // Observe only local UI mutations and decorate newly-created controls once.
  const iconObserver = new MutationObserver(mutations => {
    mutations.forEach(m => m.addedNodes.forEach(n => {
      if (n.nodeType === 1) decorateIcons(n.parentElement || n);
    }));
  });
  iconObserver.observe(document.body, { childList: true, subtree: true });
  decorateIcons(document);
  bindAuth();
  bootstrap();
})();
