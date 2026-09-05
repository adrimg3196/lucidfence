// Package version expone la versión del binario. Los valores se fijan en
// build con -ldflags "-X .../internal/version.Version=2.0.0 -X .../internal/version.Commit=abc".
package version

import (
	"fmt"
	"runtime"
)

// Version es la versión semántica del binario. "2.0.0-dev" en builds locales.
var Version = "2.0.0-dev"

// Commit es el SHA corto del commit de build. "unknown" en builds locales.
var Commit = "unknown"

// String devuelve la línea que imprime `lucidfence version`.
func String() string {
	return fmt.Sprintf("lucidfence %s (%s, %s, %s/%s)", Version, Commit, runtime.Version(), runtime.GOOS, runtime.GOARCH)
}
