/* Geofence UEM SaaS — Routes view (Task 5 of the hardening plan).
Renders the commercial route polyline + device markers colored by adherence,
plus a side list with deviation badges. Consumes GET /api/routes and
GET /api/devices (states expose route_state / route_deviation_m). */
(function () {
  "use strict";
  window.GFViews = window.GFViews || {};

  function deviationBadge(rs, devm) {
    if (rs === "off_route")
      return '<span class="tag crit">Fuera de ruta · ' + Math.round(devm || 0) + ' m</span>';
    if (rs === "on_route")
      return '<span class="tag inside">En ruta · ' + Math.round(devm || 0) + ' m</span>';
    return '<span class="tag unknown">Sin ruta asignada</span>';
  }

  GFViews.routes = async function (root, state, API, toast) {
    root.innerHTML =
      '<div class="toolbar">' +
        '<button class="btn primary" id="routeAddBtn">+ Nueva ruta</button>' +
        '<span class="chip">Corredor de tolerancia por ruta</span>' +
      '</div>' +
      '<div class="grid2">' +
        '<div class="card"><div class="hd"><h3>Mapa de rutas</h3></div>' +
          '<div id="route-map" style="height:460px"></div></div>' +
        '<div class="card"><div class="hd"><h3>Rutas asignadas</h3></div>' +
          '<div class="bd" id="route-list"></div></div>' +
      '</div>';

    const map = L.map("route-map").setView([40.42, -3.71], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { attribution: "© OpenStreetMap" }).addTo(map);

    try {
      const r = await API("GET", "/api/routes");
      const routes = (r && r.routes) || [];
      const list = document.getElementById("route-list");
      if (!routes.length) {
        list.innerHTML = '<p style="color:var(--muted-fg);font-size:13px">No hay rutas. Crea una ruta comercial y asígnala dispositivos.</p>';
      }
      routes.forEach((rt) => {
        const pts = (rt.waypoints || []).map((w) => [w.lat, w.lng]);
        if (pts.length >= 2)
          L.polyline(pts, { color: rt.color || "#22c55e", weight: 4, dashArray: "6 6" }).addTo(map);
        else if (pts.length === 1)
          L.circleMarker(pts[0], { radius: 6, color: rt.color || "#22c55e" }).addTo(map);
        const card = document.createElement("div");
        card.className = "card";
        card.style.marginBottom = "10px";
        card.innerHTML =
          "<b>" + rt.name + "</b><br>" +
          '<span style="font-size:12px;color:var(--muted-fg)">Corredor: ' +
          rt.corridor_m + " m · Dispositivos: " + (rt.device_ids || []).join(", ") + "</span>";
        list.appendChild(card);
      });

      try {
        const devs = await API("GET", "/api/devices");
        (devs || []).forEach((d) => {
          if (d.lat == null) return;
          const color = d.route_state === "off_route" ? "#ef4444"
            : d.route_state === "on_route" ? "#22c55e" : "#9ca3af";
          const m = L.circleMarker([d.lat, d.lng], { radius: 7, color: color, fillColor: color, fillOpacity: 0.9 }).addTo(map);
          m.bindPopup("<b>" + (d.name || d.device_id) + "</b><br>" + deviationBadge(d.route_state, d.route_deviation_m));
        });
      } catch (e) {
        toast("No se pudieron cargar las posiciones de los dispositivos", "bad");
      }
    } catch (e) {
      toast("No se pudieron cargar las rutas", "bad");
    }

    const add = document.getElementById("routeAddBtn");
    if (add) add.onclick = () => {
      const name = prompt("Nombre de la ruta (ej. Ruta Comercial Centro):");
      if (!name) return;
      const lat1 = parseFloat(prompt("Latitud punto 1:", "40.43"));
      const lng1 = parseFloat(prompt("Longitud punto 1:", "-3.69"));
      const lat2 = parseFloat(prompt("Latitud punto 2:", "40.42"));
      const lng2 = parseFloat(prompt("Longitud punto 2:", "-3.71"));
      const corridor = parseFloat(prompt("Corredor de tolerancia (m):", "300")) || 300;
      API("POST", "/api/routes", {
        name: name,
        waypoints: [{ lat: lat1, lng: lng1 }, { lat: lat2, lng: lng2 }],
        corridor_m: corridor,
        device_ids: [],
      }).then((res) => {
        if (res.ok) { toast("Ruta creada", "ok"); GFViews.routes(root, state, API, toast); }
        else toast(res.error || "sin permiso", "bad");
      });
    };
  };
})();
