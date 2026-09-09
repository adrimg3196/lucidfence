package notify

import "time"

// ChannelStatus es el estado acumulado de un canal de salida. Lo publica
// /api/v1/health (T15) y lo pinta la página de ajustes (T26).
type ChannelStatus struct {
	Enabled   bool       `json:"enabled"`
	Target    string     `json:"target,omitempty"`
	LastOK    *time.Time `json:"last_ok,omitempty"`
	LastError string     `json:"last_error,omitempty"`
	Delivered int        `json:"delivered"`
	Failed    int        `json:"failed"`
}

// Status agrupa el estado de los dos canales.
type Status struct {
	Webhook ChannelStatus `json:"webhook"`
	Ntfy    ChannelStatus `json:"ntfy"`
}

// Status devuelve una copia del estado: quien la recibe puede serializarla o
// modificarla sin tocar el Notifier ni verse afectado por el siguiente ciclo.
func (n *Notifier) Status() Status {
	n.mu.RLock()
	defer n.mu.RUnlock()
	return Status{Webhook: n.status.Webhook.clonar(), Ntfy: n.status.Ntfy.clonar()}
}

// clonar duplica el puntero de LastOK; copiar la estructura sin más dejaría
// al llamante mutando la fecha interna del Notifier.
func (c ChannelStatus) clonar() ChannelStatus {
	out := c
	if c.LastOK != nil {
		ok := *c.LastOK
		out.LastOK = &ok
	}
	return out
}

// registrar acumula una entrega cerrada en el estado del canal. LastOK solo
// se rellena con una entrega correcta: nunca se presenta un time.Time cero
// como si fuera un éxito.
func (n *Notifier) registrar(d Delivery) {
	n.mu.Lock()
	defer n.mu.Unlock()
	c := n.canal(d.Channel)
	if c == nil {
		return
	}
	if d.OK {
		ok := d.At
		c.Delivered++
		c.LastOK = &ok
		c.LastError = ""
		return
	}
	c.Failed++
	c.LastError = d.Error
}

// canal devuelve el estado mutable del canal, o nil si el nombre no es uno
// de los dos conocidos (no puede pasar: los planes los fija este paquete).
func (n *Notifier) canal(nombre string) *ChannelStatus {
	switch nombre {
	case ChannelWebhook:
		return &n.status.Webhook
	case ChannelNtfy:
		return &n.status.Ntfy
	default:
		return nil
	}
}
