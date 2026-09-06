// Package geo contiene la geometría esférica de LucidFence: distancias,
// pertenencia a polígono y distancia a rutas. Sin I/O. Portado de 1.x con los
// mismos casos dorados (antimeridiano, clamp a extremos).
package geo

import (
	"errors"
	"fmt"
	"math"
)

// EarthRadiusM es el radio medio terrestre usado por haversine.
const EarthRadiusM = 6_371_000.0

// Point es una coordenada WGS84 en grados.
type Point struct {
	Lat float64 `json:"lat"`
	Lng float64 `json:"lng"`
}

// NewPoint valida rango y finitud. Una geocerca es un control de seguridad:
// un NaN o un 9999 debe fallar aquí, nunca evaluarse como "fuera".
func NewPoint(lat, lng float64) (Point, error) {
	p := Point{Lat: lat, Lng: lng}
	return p, p.Valid()
}

// Valid devuelve error si la coordenada no es finita o está fuera de rango.
func (p Point) Valid() error {
	if math.IsNaN(p.Lat) || math.IsInf(p.Lat, 0) || p.Lat < -90 || p.Lat > 90 {
		return fmt.Errorf("lat fuera de rango o no finita: %v", p.Lat)
	}
	if math.IsNaN(p.Lng) || math.IsInf(p.Lng, 0) || p.Lng < -180 || p.Lng > 180 {
		return fmt.Errorf("lng fuera de rango o no finita: %v", p.Lng)
	}
	return nil
}

func rad(deg float64) float64 { return deg * math.Pi / 180 }

// HaversineM es la distancia de círculo máximo en metros.
func HaversineM(a, b Point) float64 {
	dLat := rad(b.Lat - a.Lat)
	dLng := rad(b.Lng - a.Lng)
	x := math.Pow(math.Sin(dLat/2), 2) + math.Cos(rad(a.Lat))*math.Cos(rad(b.Lat))*math.Pow(math.Sin(dLng/2), 2)
	return EarthRadiusM * 2 * math.Asin(math.Min(1, math.Sqrt(x)))
}

// unwrapLng devuelve la longitud equivalente a lng dentro de ±180° de ref,
// para que una figura que cruza el antimeridiano se trate con su anchura real.
func unwrapLng(lng, ref float64) float64 {
	return ref + math.Mod(lng-ref+180+360, 360) - 180
}

// PointInPolygon aplica ray casting. Seguro para polígonos de menos de 180°
// de longitud (toda geocerca real). El borde exacto queda indefinido.
func PointInPolygon(p Point, polygon []Point) bool {
	n := len(polygon)
	if n < 3 {
		return false
	}
	ref := polygon[0].Lng
	xs := make([]float64, n)
	ys := make([]float64, n)
	for i, v := range polygon {
		xs[i], ys[i] = unwrapLng(v.Lng, ref), v.Lat
	}
	lat, lng := p.Lat, unwrapLng(p.Lng, ref)
	inside := false
	for i, j := 0, n-1; i < n; j, i = i, i+1 {
		if (ys[i] > lat) != (ys[j] > lat) && lng < (xs[j]-xs[i])*(lat-ys[i])/(ys[j]-ys[i])+xs[i] {
			inside = !inside
		}
	}
	return inside
}

func bearing(a, b Point) float64 {
	lat1, lat2 := rad(a.Lat), rad(b.Lat)
	dLng := rad(b.Lng - a.Lng)
	y := math.Sin(dLng) * math.Cos(lat2)
	x := math.Cos(lat1)*math.Sin(lat2) - math.Sin(lat1)*math.Cos(lat2)*math.Cos(dLng)
	return math.Atan2(y, x)
}

func clamp1(v float64) float64 { return math.Max(-1, math.Min(1, v)) }

// DistanceToSegmentM es la distancia mínima de p al segmento a-b usando las
// fórmulas esféricas de cross-track y along-track, con clamp al extremo más
// cercano cuando el pie de la perpendicular cae fuera del segmento.
func DistanceToSegmentM(p, a, b Point) float64 {
	if a == b {
		return HaversineM(p, a)
	}
	dAP := HaversineM(a, p) / EarthRadiusM
	if dAP == 0 {
		return 0
	}
	delta := bearing(a, p) - bearing(a, b)
	if math.Cos(delta) < 0 {
		return HaversineM(p, a)
	}
	xt := math.Asin(clamp1(math.Sin(dAP) * math.Sin(delta)))
	cosXT := math.Cos(xt)
	at := 0.0
	if cosXT != 0 {
		at = math.Acos(clamp1(math.Cos(dAP) / cosXT))
	}
	if at > HaversineM(a, b)/EarthRadiusM {
		return HaversineM(p, b)
	}
	return math.Abs(xt) * EarthRadiusM
}

// DistanceToPolylineM es el mínimo sobre todos los segmentos; +Inf si no hay puntos.
func DistanceToPolylineM(p Point, line []Point) float64 {
	switch len(line) {
	case 0:
		return math.Inf(1)
	case 1:
		return HaversineM(p, line[0])
	}
	best := math.Inf(1)
	for i := 0; i+1 < len(line); i++ {
		best = math.Min(best, DistanceToSegmentM(p, line[i], line[i+1]))
	}
	return best
}

// ErrEmptyPolygon se usa por los validadores de dominio.
var ErrEmptyPolygon = errors.New("polígono con menos de 3 vértices")
