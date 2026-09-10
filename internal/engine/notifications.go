package engine

import (
	"context"
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/notify"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// Notifier devuelve el notificador del motor, que New siempre construye. La
// API lo usa para recargarlo en caliente al guardar los ajustes de webhooks
// (T21). Es nil solo en un Engine que un test haya construido a mano, y todo
// lo que lo consume aquí lo tolera.
func (e *Engine) Notifier() *notify.Notifier { return e.notifier }

// newNotifier devuelve el notificador de Options o, si no viene ninguno,
// construye el de la organización: sus ajustes actuales, el resolutor de
// secretos que le pasen y el propio OrgStore como Sink de deliveries.jsonl.
// Unos ajustes ilegibles dan un notificador con los de fábrica (todo
// apagado), nunca uno nil: el ciclo siguiente lo recarga con applySettings.
func newNotifier(org *store.OrgStore, opts Options) *notify.Notifier {
	if opts.Notifier != nil {
		return opts.Notifier
	}
	set := settings.Default()
	var sink notify.Sink
	if org != nil {
		// Un *store.OrgStore nil metido en la interfaz no sería nil al
		// comprobarlo dentro de notify, así que solo se envuelve el que hay.
		sink = org
		if s, err := org.Settings(); err == nil {
			set = s
		}
	}
	return notify.New(set, opts.Secrets, sink, notify.Options{Now: opts.Now, Logger: opts.Logger})
}

// notifyStatusOf publica el estado por canal para /api/v1/health y
// /api/v1/engine/status. Sin notificador, el estado es el vacío: dos canales
// deshabilitados, nunca un error inventado.
func notifyStatusOf(n *notify.Notifier) notify.Status {
	if n == nil {
		return notify.Status{}
	}
	return n.Status()
}

// alertCooldown es el silencio entre dos avisos de la misma condición sobre
// el mismo dispositivo. Es la ventana de fábrica de 1.x
// (AlertRule.cooldown_minutes = 30, lucidfence/core/alerts.py), que nunca
// mandó el mismo aviso dos veces en media hora. Sin ella una condición
// estable —un dispositivo con riesgo alto durante días— sale por webhook y
// por ntfy una vez por ciclo, para siempre. No es configurable por regla
// todavía: ese campo cambia el contrato de alerts y llega con su editor
// (M2-R41).
const alertCooldown = 30 * time.Minute

// evaluateAlerts corre las reglas de alerts.json contra la flota del ciclo y
// devuelve un evento por disparo NUEVO: el enfriamiento por regla y
// dispositivo vive aquí, en el motor, que es donde lo dejó el contrato del
// dominio ("el enfriamiento y la entrega viven fuera del dominio", package
// alert). Unas reglas ilegibles no tumban el ciclo: una alerta solo avisa,
// así que dejar de avisar es preferible a dejar de vigilar. Con las
// políticas, que sí actúan, la lectura es la contraria y el ciclo falla (T13).
func (e *Engine) evaluateAlerts(devices []device.Device, now time.Time) []notify.Event {
	rules, err := e.org.Alerts()
	if err != nil {
		e.opts.Logger.Warn("reglas de alerta ilegibles: el ciclo no las evalúa", "error", err)
		// El enfriamiento se queda como está: un fichero ilegible no es el
		// final de ningún episodio, y borrarlo haría que el ciclo siguiente
		// volviera a anunciar todo lo ya anunciado.
		return nil
	}
	firings := alert.Evaluate(rules, devices, now)
	evs := make([]notify.Event, 0, len(firings))
	// activos se reconstruye con los disparos de este ciclo: lo que ya no
	// dispara pierde la marca, así que un episodio nuevo avisa sin esperar la
	// ventana y el mapa no crece con reglas o dispositivos que ya no existen.
	activos := make(map[string]time.Time, len(firings))
	for _, f := range firings {
		k := f.RuleID + "|" + f.DeviceID
		if last, avisado := e.alerted[k]; avisado && now.Sub(last) < alertCooldown {
			activos[k] = last
			continue
		}
		cp := f
		activos[k] = now
		evs = append(evs, notify.Event{Kind: notify.EventAlertFired, At: now, Firing: &cp})
	}
	e.alerted = activos
	return evs
}

// actionEvents traduce en eventos las acciones que llegaron al conector. Una
// acción bloqueada por un guardarraíl no se ejecutó: publicarla como
// action.executed sería mentir sobre lo que pasó, y ya queda registrada en
// actions.jsonl y contada en actions_blocked.
func actionEvents(results []action.Result, now time.Time) []notify.Event {
	evs := make([]notify.Event, 0, len(results))
	for _, r := range results {
		if r.Blocked {
			continue
		}
		cp := r
		at := r.At
		if at.IsZero() {
			at = now
		}
		evs = append(evs, notify.Event{Kind: notify.EventActionExecuted, At: at, Action: &cp})
	}
	return evs
}

// dispatch entrega los eventos del ciclo y cuenta las entregas. Devuelve
// cuántas se intentaron (la cifra que notifyCycle registra en el log del
// ciclo) y no devuelve error a propósito: la red de un tercero no puede
// cambiar el resultado de un ciclo (§6.4). El recover es defensa en
// profundidad: notify.Notify ya promete no propagar pánico y el motor no
// depende de que un canal futuro mantenga esa promesa. Con el pánico
// recogido, el retorno con nombre conserva lo contado hasta ese punto.
func (e *Engine) dispatch(ctx context.Context, evs []notify.Event, st *CycleStats) (total int) {
	n := e.Notifier()
	if n == nil || len(evs) == 0 {
		return 0
	}
	defer func() {
		if r := recover(); r != nil {
			e.opts.Logger.Error("pánico entregando notificaciones", "recover", fmt.Sprint(r))
		}
	}()
	for _, ev := range evs {
		for _, d := range n.Notify(ctx, ev) {
			total++
			st.Deliveries++
			if !d.OK {
				st.DeliveriesFailed++
			}
		}
	}
	return total
}

// notifyCycle son los pasos 8 y 9 del ciclo: sincroniza los incidentes,
// evalúa las alertas y entrega todo por el Notifier, en ese orden. El
// recuento que devuelve dispatch se registra aquí: es la línea que explica
// en el log por qué un ciclo tardó lo que tardó cuando hay canales lentos.
func (e *Engine) notifyCycle(ctx context.Context, devices []device.Device, results []action.Result, now time.Time, st *CycleStats) {
	evs := e.syncIncidents(devices, results, now, st)
	alerts := e.evaluateAlerts(devices, now)
	// alerts_fired cuenta los avisos que salen, no las condiciones que siguen
	// encendidas: el enfriamiento de evaluateAlerts ya filtró.
	st.AlertsFired = len(alerts)
	evs = append(evs, alerts...)
	evs = append(evs, actionEvents(results, now)...)
	if n := e.dispatch(ctx, evs, st); n > 0 {
		e.opts.Logger.Debug("notificaciones del ciclo",
			"eventos", len(evs), "entregas", n, "fallidas", st.DeliveriesFailed)
	}
}
