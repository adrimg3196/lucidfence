package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestRunVersionImprimeVersion(t *testing.T) {
	var out, errb bytes.Buffer
	code := run([]string{"version"}, &out, &errb)
	if code != 0 {
		t.Fatalf("exit=%d stderr=%q", code, errb.String())
	}
	if !strings.HasPrefix(out.String(), "lucidfence 2.0.0-dev") {
		t.Fatalf("stdout=%q", out.String())
	}
}

func TestRunSinArgumentosMuestraUsoYFalla(t *testing.T) {
	var out, errb bytes.Buffer
	if code := run(nil, &out, &errb); code != 2 {
		t.Fatalf("exit=%d, quiero 2", code)
	}
	if !strings.Contains(errb.String(), "uso: lucidfence") {
		t.Fatalf("stderr=%q", errb.String())
	}
}

func TestRunSubcomandoDesconocido(t *testing.T) {
	var out, errb bytes.Buffer
	if code := run([]string{"nada"}, &out, &errb); code != 2 {
		t.Fatalf("exit=%d, quiero 2", code)
	}
	if !strings.Contains(errb.String(), `subcomando desconocido "nada"`) {
		t.Fatalf("stderr=%q", errb.String())
	}
}
