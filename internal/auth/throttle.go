package auth

import "time"

// El limitador de intentos de login (spec §6.2): maxFails fallos del mismo
// email dentro de failWindow lo bloquean, y el mapa que los cuenta está
// acotado a maxTrackedFailEmails claves para que una avalancha de emails
// distintos no consuma memoria sin fin.
const (
	maxFails   = 5
	failWindow = time.Minute
	// maxTrackedFailEmails acota la memoria que puede consumir el mapa de
	// fallos: sin límite, un atacante que pruebe un email distinto por
	// intento haría crecer s.fails sin fin.
	maxTrackedFailEmails = 10000
)

// throttled poda del email los intentos fuera de failWindow y decide si
// sigue bloqueado. Si no quedan intentos recientes, la clave se borra del
// mapa en vez de dejar una entrada vacía indefinidamente.
func (s *Store) throttled(email string) bool {
	cutoff := s.now().Add(-failWindow)
	var recent []time.Time
	for _, t := range s.fails[email] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	if len(recent) == 0 {
		delete(s.fails, email)
	} else {
		s.fails[email] = recent
	}
	return len(recent) >= maxFails
}

// registerFail anota un intento fallido. El mapa sigue acotado a
// maxTrackedFailEmails claves (una avalancha de emails distintos no puede
// hacerlo crecer sin fin), pero hacer hueco nunca reinicia el contador de
// un email ya bloqueado: vaciar el mapa entero al llegar al tope permitía
// saltarse el límite de la spec §6.2 a voluntad, porque inundar con emails
// inexistentes es barato (ese camino ni siquiera deriva argon2). Un email
// ya seguido siempre se anota; uno nuevo, solo si makeRoomForFail
// encuentra sitio.
func (s *Store) registerFail(email string) {
	if _, tracked := s.fails[email]; !tracked && !s.makeRoomForFail() {
		return
	}
	s.fails[email] = append(s.fails[email], s.now())
}

// makeRoomForFail deja hueco para una clave nueva en el mapa de fallos:
// primero borra las entradas caducadas (su último intento cae fuera de
// failWindow, así que ya no cuentan para throttled) y, si el mapa sigue
// lleno, expulsa la más antigua de entre las que todavía no bloquean
// (menos de maxFails intentos). Devuelve false si todas las entradas están
// bloqueando: antes que soltar a una víctima, se prefiere no seguir la
// clave nueva.
func (s *Store) makeRoomForFail() bool {
	if len(s.fails) < maxTrackedFailEmails {
		return true
	}
	cutoff := s.now().Add(-failWindow)
	for email, ts := range s.fails {
		if len(ts) == 0 || !ts[len(ts)-1].After(cutoff) {
			delete(s.fails, email)
		}
	}
	for len(s.fails) >= maxTrackedFailEmails {
		oldest, at, found := "", time.Time{}, false
		for email, ts := range s.fails {
			if len(ts) >= maxFails {
				continue
			}
			if last := ts[len(ts)-1]; !found || last.Before(at) {
				oldest, at, found = email, last, true
			}
		}
		if !found {
			return false
		}
		delete(s.fails, oldest)
	}
	return true
}
