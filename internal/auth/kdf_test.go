package auth

import (
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// TestKDFConcurrenciaAcotada comprueba que Login nunca deja más de
// maxConcurrentKDF derivaciones argon2id en curso a la vez: sustituye
// verifyPassword por una función que cuenta cuántas invocaciones están
// activas (con un atómico), registra el máximo observado y espera 20 ms
// antes de terminar, para dar tiempo a que las 16 llamadas concurrentes se
// solapen. Sin el semáforo de acquireKDF/releaseKDF, las 16 correrían a la
// vez y el máximo observado superaría maxConcurrentKDF.
func TestKDFConcurrenciaAcotada(t *testing.T) {
	s, _ := openStore(t)
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}

	var current, max int64
	s.verifyPassword = func(_, _ string) bool {
		n := atomic.AddInt64(&current, 1)
		for {
			prev := atomic.LoadInt64(&max)
			if n <= prev || atomic.CompareAndSwapInt64(&max, prev, n) {
				break
			}
		}
		time.Sleep(20 * time.Millisecond)
		atomic.AddInt64(&current, -1)
		return false
	}

	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = s.Login("a@x.com", "mal", "default")
		}()
	}
	wg.Wait()

	if got := atomic.LoadInt64(&max); got > maxConcurrentKDF {
		t.Fatalf("derivaciones argon2id concurrentes = %d, quería <= %d", got, maxConcurrentKDF)
	}
}

// TestLoginLeeOrgRolesBajoElLock comprueba, con -race, que Login y Setup
// pueden ejecutarse concurrentemente sin que el acceso a OrgRoles (un mapa
// compartido por referencia entre userRecord y la copia que Login toma bajo
// el lock) dispare un aviso del detector de razas. El resultado de cada
// Login que corre antes de que Setup termine es indiferente (credenciales
// inválidas o incluso throttle son correctos si el usuario aún no existe);
// lo único que importa es que no haya panic ni aviso de carrera y que Setup
// acabe creando el usuario. No hay todavía una API que modifique OrgRoles
// tras la creación, así que esto no reproduce una carrera real; fija la
// disciplina de "el mapa no se toca fuera de la sección crítica" para que
// una futura API de cambio de rol no la rompa en silencio.
func TestLoginLeeOrgRolesBajoElLock(t *testing.T) {
	s, _ := openStore(t)

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
			t.Errorf("setup: %v", err)
		}
	}()
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = s.Login("a@x.com", "contraseña-larga-1", "default")
		}()
	}
	wg.Wait()

	if !s.HasUsers() {
		t.Fatal("el setup concurrente no creó el usuario")
	}
}
