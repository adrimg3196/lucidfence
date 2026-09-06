package main

import (
	"bytes"
	"context"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sync"
	"testing"
	"time"
)

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

// syncBuffer envuelve bytes.Buffer con un mutex: serve escribe desde su
// propia goroutine mientras el test sondea el contenido desde la suya, y un
// bytes.Buffer desnudo compartido así es una carrera de datos bajo -race.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

func TestServeArrancaImprimeDireccionYParaConContexto(t *testing.T) {
	dir := t.TempDir()
	var out, errb syncBuffer
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan int)
	go func() {
		done <- serve(ctx, commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data"), Listen: "127.0.0.1:0"}, true, &out, &errb)
	}()
	re := regexp.MustCompile(`listening on (http://127\.0\.0\.1:\d+)`)
	var url string
	for deadline := time.Now().Add(5 * time.Second); time.Now().Before(deadline) && url == ""; {
		if m := re.FindStringSubmatch(out.String()); m != nil {
			url = m[1]
		}
		time.Sleep(20 * time.Millisecond)
	}
	if url == "" {
		t.Fatalf("no imprimió la dirección: %q %q", out.String(), errb.String())
	}
	res, err := http.Get(url + "/api/v1/health")
	if err != nil || res.StatusCode != 200 {
		t.Fatalf("health: %v %v", err, res)
	}
	_ = res.Body.Close()
	cancel()
	select {
	case code := <-done:
		if code != 0 {
			t.Fatalf("exit=%d stderr=%s", code, errb.String())
		}
	case <-time.After(15 * time.Second):
		t.Fatal("serve no terminó tras cancelar")
	}
}

func TestServePuertoOcupadoFalla(t *testing.T) {
	dir := t.TempDir()
	var out, errb bytes.Buffer
	ln, _ := (&netListenConfig{}).listen("127.0.0.1:0")
	defer func() { _ = ln.Close() }()
	code := serve(context.Background(), commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data"), Listen: ln.Addr().String()}, false, &out, &errb)
	if code != 1 || !bytes.Contains(errb.Bytes(), []byte("no se puede escuchar")) {
		t.Fatalf("exit=%d stderr=%q", code, errb.String())
	}
}
