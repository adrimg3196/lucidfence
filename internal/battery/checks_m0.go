package battery

import (
	"context"
	"fmt"
	"strings"
)

func checksM0() []Check {
	return []Check{
		{Name: "version imprime lucidfence y la versión", Run: checkVersion},
	}
}

func checkVersion(ctx context.Context, env *Env) error {
	out, err := runBin(ctx, env, "version")
	if err != nil {
		return fmt.Errorf("%v: %s", err, out)
	}
	if !strings.HasPrefix(out, "lucidfence 2.") {
		return fmt.Errorf("salida inesperada: %q", out)
	}
	return nil
}
