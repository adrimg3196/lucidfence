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
