// Package notify entrega los eventos de LucidFence al exterior: webhook firmado
// HMAC-SHA256, formato OCSF y ntfy. Es un servicio hoja: solo importa domain y
// store (ARCHITECTURE.md, "Reglas de dependencia"; spec §5.2), y nunca al
// revés: el motor lo llama, él no llama al motor.
//
// Toda salida a la red del producto pasa antes por Egress.Check, la única
// puerta de egress: host en la allowlist, resolución DNS única y rechazo de
// direcciones privadas salvo allow_private (spec §5.6).
package notify

import (
	"log/slog"
	"time"
)

// UserAgent identifica al producto en toda petición saliente; T10 lo pone en la
// cabecera User-Agent del webhook y de ntfy.
const UserAgent = "LucidFence/2.0"

// DefaultTimeout es el tiempo máximo de una entrega completa (conexión,
// handshake y respuesta). T11 lo usa como valor por defecto de la cola.
const DefaultTimeout = 10 * time.Second

// defaultLogger evita repartir comprobaciones de nil: sin logger explícito se
// usa el global, para que una denegación nunca quede sin registrar.
func defaultLogger(l *slog.Logger) *slog.Logger {
	if l != nil {
		return l
	}
	return slog.Default()
}
