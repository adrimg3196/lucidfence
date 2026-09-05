// Command battery ejecuta la batería runtime contra un binario lucidfence.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/battery"
)

func main() {
	bin := flag.String("bin", "bin/lucidfence", "ruta al binario lucidfence")
	timeout := flag.Duration("timeout", 3*time.Minute, "tiempo máximo total")
	flag.Parse()
	tmp, err := os.MkdirTemp("", "lucidfence-battery-*")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer func() { _ = os.RemoveAll(tmp) }()
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	passed, total := battery.Run(ctx, &battery.Env{Bin: *bin, Tmp: tmp}, battery.Checks(), os.Stdout)
	if passed != total {
		os.Exit(1)
	}
}
