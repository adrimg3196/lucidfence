/* LucidFence Whitelabel UI — DigitalPlat FreeDomain + Atomic Mail.
   Self-contained: login, suggest DNS, save, live validate. No frameworks. */
(function () {
  const $ = (id) => document.getElementById(id);
  let cookies = "";

  function api(path, opts) {
    opts = opts || {};
    return fetch(path, Object.assign({
      method: opts.method || "GET",
      headers: Object.assign({ "Content-Type": "application/json" }, opts.headers || {}),
      credentials: "same-origin",
    }, opts.body ? { body: JSON.stringify(opts.body) } : {}));
  }

  function setStatus(el, msg, cls) {
    el.textContent = msg;
    el.className = "status " + (cls || "");
    el.style.display = msg ? "block" : "none";
  }

  async function login() {
    const email = $("email").value.trim();
    const password = $("password").value;
    setStatus($("loginStatus"), "Conectando…");
    // Try login; if it fails (no account), signup.
    let r = await api("/api/auth/login", { method: "POST", body: { email, password } });
    if (!r.ok) {
      r = await api("/api/auth/signup", {
        method: "POST",
        body: { email, name: email.split("@")[0], password, org_name: "AcmeFenceWL" },
      });
    }
    if (r.ok) {
      cookies = document.cookie;
      setStatus($("loginStatus"), "Sesión iniciada.", "ok");
      $("wlPanel").style.display = "block";
      $("senderPanel").style.display = "block";
      await refreshStatus();
    } else {
      const e = await r.json().catch(() => ({}));
      setStatus($("loginStatus"), "Error: " + (e.error || r.status), "err");
    }
  }

  async function refreshStatus() {
    const r = await api("/api/whitelabel/status");
    if (!r.ok) return;
    const s = await r.json();
    if (s.configured) {
      $("domain").value = s.domain;
      $("selector").value = s.dkim_selector || "atomicmail";
      $("dashTarget").value = s.dashboard_target || "";
    }
    if (s.sender) {
      $("senderInfo").innerHTML = "Remitente: <code>" + s.sender + "</code>" +
        (s.last_validation ? ' <span class="pill">última validación: ' + s.last_validation.overall + "</span>" : "");
    }
  }

  async function suggest() {
    const domain = $("domain").value.trim();
    if (!domain) return setStatus($("wlStatus"), "Escribe un dominio.", "err");
    const r = await api("/api/whitelabel/suggest", {
      method: "POST",
      body: {
        domain,
        dkim_selector: $("selector").value.trim() || "atomicmail",
        dashboard_target: $("dashTarget").value.trim(),
        receive_mail: true,
      },
    });
    const j = await r.json();
    if (!r.ok) return setStatus($("wlStatus"), "Error: " + (j.error || r.status), "err");
    const tb = $("recTable").getElementsByTagName("tbody")[0];
    tb.innerHTML = "";
    j.suggestion.records.forEach((rec) => {
      const tr = document.createElement("tr");
      tr.innerHTML = "<td>" + rec.type + "</td><td><code>" + rec.name + "</code></td><td><code>" +
        rec.value + "</code></td><td>" + rec.purpose + "</td>";
      tb.appendChild(tr);
    });
    $("suggestOut").style.display = "block";
    setStatus($("wlStatus"), "Registros generados. Crea estos en tu panel DNS (Cloudflare/DigitalPlat).", "ok");
  }

  async function save() {
    const domain = $("domain").value.trim();
    if (!domain) return setStatus($("wlStatus"), "Escribe un dominio.", "err");
    const r = await api("/api/whitelabel/setup", {
      method: "POST",
      body: {
        domain,
        dkim_selector: $("selector").value.trim() || "atomicmail",
        dashboard_target: $("dashTarget").value.trim(),
      },
    });
    const j = await r.json();
    if (!r.ok) return setStatus($("wlStatus"), "Error: " + (j.error || r.status), "err");
    $("senderInfo").innerHTML = "Remitente: <code>" + j.sender + "</code>";
    setStatus($("wlStatus"), "Whitelabel guardado. Remitente: " + j.sender, "ok");
  }

  async function validate() {
    const r = await api("/api/whitelabel/validate", { method: "POST", body: {} });
    const j = await r.json();
    if (!r.ok) return setStatus($("wlStatus"), "Error: " + (j.error || r.status), "err");
    const rep = j.report;
    const cls = rep.overall === "ok" ? "ok" : (rep.overall === "partial" ? "partial" : "missing");
    $("validatePre").textContent = JSON.stringify(rep, null, 2);
    $("validateOut").style.display = "block";
    const checks = ["NS:" + rep.ns_delegated, "SPF:" + rep.spf, "DKIM:" + rep.dkim, "DMARC:" + rep.dmarc].join("  ·  ");
    setStatus($("wlStatus"), "Validación: " + rep.overall.toUpperCase() + "  (" + checks + ")", cls);
  }

  window.addEventListener("DOMContentLoaded", function () {
    $("loginBtn").addEventListener("click", login);
    $("suggestBtn").addEventListener("click", suggest);
    $("saveBtn").addEventListener("click", save);
    $("validateBtn").addEventListener("click", validate);
  });
})();
