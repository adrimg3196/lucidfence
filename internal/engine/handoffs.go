package engine

import (
	"context"
	"errors"
	"fmt"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
)

// Centinelas de las dos entradas manuales. T20 los traduce a códigos HTTP:
// not_found, conflict y cooldown. ErrActionBlocked no es un error de la
// petición sino un resultado con motivo, y viaja junto a un action.Result
// relleno para que la API responda 200 con el bloqueo dentro.
var (
	ErrHandoffNotFound  = errors.New("handoff no encontrado")
	ErrHandoffDecided   = errors.New("handoff ya decidido")
	ErrDeviceNotFound   = errors.New("dispositivo no encontrado")
	ErrActionSuppressed = errors.New("acción suprimida por cooldown")
	ErrActionBlocked    = errors.New("acción bloqueada por guardarraíl")
)

// ApproveHandoff aprueba una petición y ejecuta su acción PASANDO POR LOS
// GUARDARRAÍLES: la aprobación humana autoriza el intento, no abre la doble
// llave del wipe ni saca al motor de observe. En observe la orden sale en
// dry-run; sin allow_wipe, un wipe aprobado queda bloqueado y el conector no
// lo ve. El resultado se guarda dentro del handoff, que pasa a executed, y
// queda registrado en actions.jsonl con el actor.
//
// La decisión se persiste ANTES de ejecutar: si el proceso se cae en medio, lo
// que sobrevive es lo que dijo la persona.
func (e *Engine) ApproveHandoff(ctx context.Context, id, by, note string) (playbook.Handoff, error) {
	e.manualMu.Lock()
	defer e.manualMu.Unlock()
	h, err := e.decideHandoff(id, playbook.HandoffApproved, by, note)
	if err != nil {
		return h, err
	}
	d, err := e.deviceByID(h.DeviceID)
	if err != nil {
		return h, err
	}
	res, err := e.runManual(ctx, Planned{Device: d, Action: h.Action, Params: h.Params,
		FenceID: d.InsideFence, PlaybookID: h.PlaybookID, Trigger: TriggerHandoff,
		Severity: h.Severity}, by)
	if err != nil && !errors.Is(err, ErrActionBlocked) {
		// Suprimida por cooldown: no hubo intento y no hay resultado que
		// enseñar. La petición se queda en approved, lista para reintentarse
		// cuando expire la ventana.
		return h, err
	}
	done, derr := h.Decide(playbook.HandoffExecuted, by, "", e.opts.Now().UTC())
	if derr != nil {
		return h, derr
	}
	done.Result = &res
	return done, e.saveHandoff(done)
}

// RejectHandoff cierra la petición sin tocar el conector: un rechazo no
// ejecuta nada, ni siquiera en dry-run. No usa el contexto (no hay llamada al
// UEM), pero conserva el parámetro para que las dos decisiones tengan la misma
// firma en la API.
func (e *Engine) RejectHandoff(_ context.Context, id, by, note string) (playbook.Handoff, error) {
	e.manualMu.Lock()
	defer e.manualMu.Unlock()
	return e.decideHandoff(id, playbook.HandoffRejected, by, note)
}

// ExecuteManual es la vía de POST /devices/{id}/actions: la acción que lanza
// una persona desde el detalle del dispositivo. Recorre exactamente el mismo
// camino que el ciclo (guardarraíles, conector y registro en actions.jsonl con
// el actor), así que un wipe en observe sale en dry-run y uno sin la doble
// llave sale bloqueado. Aquí no hay handoff que abrir: la capacidad
// device:action y la sesión que firma la petición SON el gate humano.
func (e *Engine) ExecuteManual(ctx context.Context, deviceID string, a action.Action,
	params map[string]any, by string) (action.Result, error) {
	e.manualMu.Lock()
	defer e.manualMu.Unlock()
	d, err := e.deviceByID(deviceID)
	if err != nil {
		return action.Result{}, err
	}
	return e.runManual(ctx, Planned{Device: d, Action: a, Params: params,
		FenceID: d.InsideFence, Trigger: TriggerManual}, by)
}

// runManual pasa una orden por los guardarraíles fuera del ciclo y la
// registra. Relee settings.json antes de decidir porque una entrada manual
// puede llegar segundos después de que la API cambie el enforcement, y esperar
// al ciclo siguiente dejaría salir en vivo una orden que el operador acaba de
// restringir (o al revés). Las estadísticas que rellena apply se descartan: no
// hay ciclo al que sumarlas.
func (e *Engine) runManual(ctx context.Context, p Planned, by string) (action.Result, error) {
	e.applySettings(e.settingsOrDefault())
	var st CycleStats
	res, logged := e.apply(ctx, p, &st)
	if !logged {
		return action.Result{}, fmt.Errorf("%w: %s en %s", ErrActionSuppressed, p.Action, p.Device.ID)
	}
	res.Note = withActor(res.Note, by)
	if err := e.org.AppendAction(res); err != nil {
		e.opts.Logger.Warn("persistencia", "op", "action", "device", p.Device.ID, "error", err)
	}
	if res.Blocked {
		return res, fmt.Errorf("%w: %s", ErrActionBlocked, res.Error)
	}
	return res, nil
}

// withActor deja en la nota del resultado quién pidió la acción. Es el único
// sitio donde cabe: action.Result es el formato de auditoría congelado en M1 y
// añadirle un campo obligaría a versionar actions.jsonl.
func withActor(note, by string) string {
	switch {
	case by == "":
		return note
	case note == "":
		return "actor: " + by
	default:
		return note + " · actor: " + by
	}
}

// deviceByID busca el dispositivo en devices.json, que es la foto del último
// ciclo: las entradas manuales actúan sobre lo que el motor sabe, no sobre lo
// que un cliente diga.
func (e *Engine) deviceByID(id string) (device.Device, error) {
	ds, err := e.org.Devices()
	if err != nil {
		return device.Device{}, err
	}
	d, ok := device.Index(ds)[id]
	if !ok {
		return device.Device{}, fmt.Errorf("%w: %q", ErrDeviceNotFound, id)
	}
	return d, nil
}

// decideHandoff aplica una transición del gate humano y la persiste. Si la
// máquina de estados de T6 la rechaza (la petición ya estaba decidida),
// devuelve el handoff tal como está para que la API pueda explicar el
// conflicto con su dispositivo y su acción.
func (e *Engine) decideHandoff(id string, to playbook.HandoffStatus, by, note string) (playbook.Handoff, error) {
	hs, err := e.org.Handoffs()
	if err != nil {
		return playbook.Handoff{}, err
	}
	i := indexOfHandoff(hs, id)
	if i < 0 {
		return playbook.Handoff{}, fmt.Errorf("%w: %q", ErrHandoffNotFound, id)
	}
	h, derr := hs[i].Decide(to, by, note, e.opts.Now().UTC())
	if derr != nil {
		return hs[i], fmt.Errorf("%w: %v", ErrHandoffDecided, derr)
	}
	hs[i] = h
	if err := e.org.SaveHandoffs(hs); err != nil {
		return h, err
	}
	return h, nil
}

// saveHandoff reemplaza la petición en la bandeja conservando el resto.
func (e *Engine) saveHandoff(h playbook.Handoff) error {
	hs, err := e.org.Handoffs()
	if err != nil {
		return err
	}
	return e.org.SaveHandoffs(playbook.Upsert(hs, h))
}

// indexOfHandoff localiza por id; -1 si no está.
func indexOfHandoff(hs []playbook.Handoff, id string) int {
	for i := range hs {
		if hs[i].ID == id {
			return i
		}
	}
	return -1
}
