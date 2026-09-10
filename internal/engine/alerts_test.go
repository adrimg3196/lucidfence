package engine

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/notify"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// reglaFuera deja en alerts.json una única regla que dispara mientras el
// dispositivo esté fuera de su geocerca (umbral 0 minutos): es la condición
// más fácil de encender y apagar desde el conector, y sustituye a la regla de
// riesgo que sembró SeedDemo para que el disparo no dependa del score.
func reglaFuera(t *testing.T, org *store.OrgStore, now time.Time) {
	t.Helper()
	if err := org.SaveAlerts([]alert.Rule{{
		ID: "fuera-de-geocerca", Name: "Fuera de geocerca", Kind: alert.KindOutsideDuration,
		Threshold: 0, Severity: risk.SeverityHigh, Enabled: true, CreatedAt: now, UpdatedAt: now,
	}}); err != nil {
		t.Fatal(err)
	}
}

// cicloDeAlertas corre un ciclo y comprueba dos cosas a la vez: cuántos
// avisos declara el ciclo (alerts_fired) y cuántos webhooks alert.fired lleva
// vistos el receptor en total. La segunda cifra es la que le importa a quien
// recibe: el contador podría mentir y las entregas no.
func cicloDeAlertas(t *testing.T, e *Engine, rec *receptor, avisos, entregados int, motivo string) {
	t.Helper()
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.AlertsFired != avisos {
		t.Fatalf("%s: alerts_fired=%d, quiero %d", motivo, st.AlertsFired, avisos)
	}
	if got := len(rec.porEvento(notify.EventAlertFired)); got != entregados {
		t.Fatalf("%s: %d entregas alert.fired acumuladas, quiero %d", motivo, got, entregados)
	}
}

// TestUnaCondicionQuePersisteNoAvisaEnCadaCiclo es el enfriamiento de 1.x
// (AlertRule.cooldown_minutes = 30, lucidfence/core/alerts.py) portado al
// motor, donde el contrato del paquete alert lo puso ("el enfriamiento y la
// entrega viven fuera del dominio"). Sin él, un dispositivo con la condición
// encendida manda un webhook firmado por ciclo mientras siga encendida: con
// el intervalo mínimo de 10 s, 360 a la hora.
func TestUnaCondicionQuePersisteNoAvisaEnCadaCiclo(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	ad := nuevaFlotaMovil(fueraHQ)
	clock := &reloj{at: time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)}
	e, org := motorNotificadoEn(t, ajustesWebhook(url, settings.FormatNative, []string{notify.EventAlertFired}), ad, clock)
	reglaFuera(t, org, clock.now())

	cicloDeAlertas(t, e, rec, 1, 1, "la condición aparece: se avisa")
	clock.avanzar(time.Minute)
	cicloDeAlertas(t, e, rec, 0, 1, "un minuto después sigue igual: no se repite el aviso")
	clock.avanzar(alertCooldown)
	cicloDeAlertas(t, e, rec, 1, 2, "pasada la ventana se recuerda: la condición sigue viva")
}

// TestUnaCondicionQueSeApagaVuelveAAvisarAlReaparecer es la otra mitad: el
// enfriamiento no puede convertirse en un silencio permanente. Un episodio
// nuevo —el dispositivo vuelve a salir— es noticia aunque no haya pasado la
// ventana, porque la marca se borra en cuanto la regla deja de disparar.
func TestUnaCondicionQueSeApagaVuelveAAvisarAlReaparecer(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	ad := nuevaFlotaMovil(fueraHQ)
	clock := &reloj{at: time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)}
	e, org := motorNotificadoEn(t, ajustesWebhook(url, settings.FormatNative, []string{notify.EventAlertFired}), ad, clock)
	reglaFuera(t, org, clock.now())

	cicloDeAlertas(t, e, rec, 1, 1, "fuera de la geocerca: primer aviso")
	ad.mover(dentroHQ)
	clock.avanzar(time.Minute)
	cicloDeAlertas(t, e, rec, 0, 1, "dentro no hay nada que avisar: el episodio se cierra")
	ad.mover(fueraHQ)
	clock.avanzar(time.Minute)
	cicloDeAlertas(t, e, rec, 1, 2, "una salida nueva es noticia aunque no haya pasado la ventana")
}
