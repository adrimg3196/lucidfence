/* Vista "Workflows" — apartado de lógica de workflows integrados.
   Plantillas ya hechas (un click para activar) + creación fácil por admin IT.
   Consume GET /api/workflows y POST /api/workflows/apply | /custom | /<id>/delete.
   Asume globals: API (helper fetch), toast (fn), goView (fn). */
window.GFViews = window.GFViews || {};
GFViews.workflows = function (root, state, API, toast) {
  root.innerHTML = `
    <div class="view-head">
      <div>
        <h2>Workflows integrados</h2>
        <p class="muted">Lógica lista para Applivery. Activa una plantilla o crea una propia sin tocar JSON.</p>
      </div>
    </div>
    <div class="workflow-grid">
      <div class="wf-col">
        <h3>Plantillas comunes</h3>
        <div id="wf-templates" class="wf-cards"></div>
      </div>
      <div class="wf-col">
        <h3>Creación fácil (admin IT)</h3>
        <div class="card" id="wf-builder">
          <label>Nombre del workflow</label>
          <input id="wf-name" class="inp" placeholder="Ej: Bloquear si rooteado" />
          <label>Disparador (trigger)</label>
          <select id="wf-trigger" class="inp"></select>
          <div id="wf-devbox" style="display:none">
            <label>Desviación mínima (m) — opcional</label>
            <input id="wf-dev" class="inp" type="number" placeholder="500" />
          </div>
          <label>Acción en Applivery</label>
          <select id="wf-action" class="inp"></select>
          <div id="wf-msgbox" style="display:none">
            <label>Texto del mensaje / aviso</label>
            <input id="wf-msg" class="inp" placeholder="Aviso de cumplimiento" />
          </div>
          <label>Severidad</label>
          <select id="wf-sev" class="inp">
            <option value="low">Baja</option>
            <option value="medium" selected>Media</option>
            <option value="high">Alta</option>
            <option value="critical">Crítica</option>
          </select>
          <div id="wf-custombox" style="display:none">
            <label>Tipo de comando custom (endpoint Applivery)</label>
            <input id="wf-customtype" class="inp" placeholder="p. ej. lock_app" />
            <label>Argumentos (JSON o texto)</label>
            <input id="wf-customargs" class="inp" placeholder='{"app_id":"com.x"}' />
          </div>
          <div id="wf-devidsbox">
            <label>Dispositivos (opcional, separa por coma). Vacío = todos.</label>
            <input id="wf-devids" class="inp" placeholder="dev-001, dev-002" />
          </div>
          <button class="btn primary" id="wf-create" style="margin-top:10px">Crear workflow</button>
        </div>
        <h3 style="margin-top:18px">Activos</h3>
        <div id="wf-active" class="wf-active"></div>
      </div>
    </div>`;

  const tplBox = root.querySelector("#wf-templates");
  const trigSel = root.querySelector("#wf-trigger");
  const actSel = root.querySelector("#wf-action");
  const devBox = root.querySelector("#wf-devbox");
  const msgBox = root.querySelector("#wf-msgbox");
  const customBox = root.querySelector("#wf-custombox");
  const activeBox = root.querySelector("#wf-active");

  function renderActive(list) {
    if (!list.length) {
      activeBox.innerHTML = `<p class="muted">Ningún workflow activo todavía.</p>`;
      return;
    }
    activeBox.innerHTML = list.map(w => `
      <div class="wf-active-item">
        <div>
          <strong>${esc(w.name)}</strong>
          <span class="tag tag-${esc(w.severity || 'medium')}">${esc(w.severity || 'medium')}</span>
          <span class="tag">${esc(w.source === 'custom' ? 'propio' : 'plantilla')}</span>
        </div>
        <button class="btn small danger" data-del="${esc(w.id)}">Desactivar</button>
      </div>`).join("");
    activeBox.querySelectorAll("[data-del]").forEach(b => {
      b.onclick = async () => {
        await API("POST", `/api/workflows/${b.dataset.del}/delete`);
        toast("Workflow desactivado", "ok");
        load();
      };
    });
  }

  async function load() {
    const data = await API("GET", "/api/workflows");
    if (!data || data.error) { toast("Sin permiso para workflows", "bad"); return; }
    // plantillas
    tplBox.innerHTML = data.templates.map(t => `
      <div class="wf-card">
        <strong>${esc(t.name)}</strong>
        <p class="muted">${esc(t.summary)}</p>
        <div class="wf-actions-preview">${t.actions.map(a => `<span class="tag">${esc(a.action)}</span>`).join(" ")}</div>
        <button class="btn small primary" data-apply="${esc(t.id)}">Activar</button>
      </div>`).join("");
    tplBox.querySelectorAll("[data-apply]").forEach(b => {
      b.onclick = async () => {
        const r = await API("POST", "/api/workflows/apply", { template_id: b.dataset.apply });
        if (r && r.ok) { toast("Plantilla activada: " + b.dataset.apply, "ok"); load(); }
        else toast("No se pudo activar (¿permiso?)", "bad");
      };
    });
    // selects
    trigSel.innerHTML = data.triggers.map(o => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join("");
    actSel.innerHTML = data.actions.map(o => `<option value="${esc(o.value)}" title="${esc(o.desc || '')}">${esc(o.label)}</option>`).join("");
    renderActive(data.active || []);
  }

  trigSel.onchange = () => { devBox.style.display = trigSel.value === "route_exit" ? "block" : "none"; };
  actSel.onchange = () => {
    msgBox.style.display = (actSel.value === "message" || actSel.value === "notify") ? "block" : "none";
    customBox.style.display = actSel.value === "custom" ? "block" : "none";
  };

  root.querySelector("#wf-create").onclick = async () => {
    const name = root.querySelector("#wf-name").value.trim();
    if (!name) { toast("Ponle un nombre al workflow", "bad"); return; }
    const body = {
      name,
      trigger: trigSel.value,
      action: actSel.value,
      severity: root.querySelector("#wf-sev").value,
    };
    if (trigSel.value === "route_exit") {
      const d = root.querySelector("#wf-dev").value;
      if (d) body.min_deviation_m = parseInt(d, 10);
    }
    if (actSel.value === "message" || actSel.value === "notify") {
      body.action_text = root.querySelector("#wf-msg").value.trim();
    }
    if (actSel.value === "custom") {
      body.custom_type = root.querySelector("#wf-customtype").value.trim() || "custom";
      body.custom_args = root.querySelector("#wf-customargs").value.trim();
    }
    const devids = root.querySelector("#wf-devids").value.trim();
    if (devids) {
      body.device_ids = devids.split(",").map(s => s.trim()).filter(Boolean);
    }
    const r = await API("POST", "/api/workflows/custom", body);
    if (r && r.ok) { toast("Workflow creado", "ok"); load(); }
    else toast("Error: " + ((r && r.error) || "desconocido"), "bad");
  };

  load();
};
