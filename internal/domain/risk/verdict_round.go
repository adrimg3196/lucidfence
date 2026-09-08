package risk

import (
	"math"
	"math/big"
)

// roundTenth redondea el valor binary64 exacto a la décima par más cercana.
// Escalar primero en float64 perdería bits (p.ej. 1.15). El cociente y resto
// son enteros exactos y q/10 se convierte una sola vez a binary64.
// Evaluate llama exclusivamente con un valor finito acotado en [0,100].
func roundTenth(v float64) float64 {
	if v == 0 || math.IsNaN(v) || math.IsInf(v, 0) {
		return v
	}
	r := new(big.Rat).SetFloat64(math.Abs(v))
	n := new(big.Int).Mul(r.Num(), big.NewInt(10))
	q, rem := new(big.Int), new(big.Int)
	q.QuoRem(n, r.Denom(), rem)
	comparison := new(big.Int).Lsh(rem, 1).Cmp(r.Denom())
	if comparison > 0 || (comparison == 0 && q.Bit(0) == 1) {
		q.Add(q, big.NewInt(1))
	}
	out, _ := new(big.Rat).SetFrac(q, big.NewInt(10)).Float64()
	return math.Copysign(out, v)
}
