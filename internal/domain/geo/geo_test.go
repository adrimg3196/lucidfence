package geo

import (
	"math"
	"testing"
)

func near(t *testing.T, got, want, tol float64, msg string) {
	t.Helper()
	if math.Abs(got-want) > tol {
		t.Fatalf("%s: got %.3f want %.3f (±%.3f)", msg, got, want, tol)
	}
}

func TestNewPointRechazaValoresInvalidos(t *testing.T) {
	bad := [][2]float64{{91, 0}, {-91, 0}, {0, 181}, {0, -181}, {math.NaN(), 0}, {0, math.Inf(1)}}
	for _, c := range bad {
		if _, err := NewPoint(c[0], c[1]); err == nil {
			t.Fatalf("NewPoint(%v) debería fallar", c)
		}
	}
	if _, err := NewPoint(40.42, -3.71); err != nil {
		t.Fatal(err)
	}
}

func TestHaversineCasosDorados(t *testing.T) {
	near(t, HaversineM(Point{0, 0}, Point{0, 1}), 111194.93, 0.5, "1 grado de longitud en el ecuador")
	near(t, HaversineM(Point{0, 0}, Point{1, 0}), 111194.93, 0.5, "1 grado de latitud")
	near(t, HaversineM(Point{0, 0}, Point{0, 180}), math.Pi*EarthRadiusM, 1, "antípoda")
	near(t, HaversineM(Point{40.42, -3.71}, Point{40.42, -3.71}), 0, 0, "mismo punto")
	near(t, HaversineM(Point{40.4168, -3.7038}, Point{40.4200, -3.7100}), 634, 3, "Sol a Plaza de España aprox")
}

func TestPointInPolygonCuadradoYConcavo(t *testing.T) {
	square := []Point{{40.40, -3.72}, {40.40, -3.70}, {40.44, -3.70}, {40.44, -3.72}}
	if !PointInPolygon(Point{40.42, -3.71}, square) {
		t.Fatal("centro del cuadrado debe estar dentro")
	}
	if PointInPolygon(Point{40.45, -3.71}, square) {
		t.Fatal("fuera por el norte")
	}
	// Forma en L: (0,0)-(2,0)-(2,1)-(1,1)-(1,2)-(0,2). El punto (1.5,1.5) está en el hueco.
	l := []Point{{0, 0}, {0, 2}, {1, 2}, {1, 1}, {2, 1}, {2, 0}}
	if !PointInPolygon(Point{0.5, 0.5}, l) {
		t.Fatal("(0.5,0.5) dentro de la L")
	}
	if PointInPolygon(Point{1.5, 1.5}, l) {
		t.Fatal("(1.5,1.5) en el hueco de la L")
	}
	if PointInPolygon(Point{0, 0}, []Point{{0, 0}, {1, 1}}) {
		t.Fatal("menos de 3 vértices nunca contiene")
	}
}

func TestPointInPolygonAntimeridiano(t *testing.T) {
	// Cuadrado de 4° de ancho que cruza lng ±180.
	poly := []Point{{-1, 178}, {-1, -178}, {1, -178}, {1, 178}}
	if !PointInPolygon(Point{0, 179.5}, poly) || !PointInPolygon(Point{0, -179.5}, poly) {
		t.Fatal("puntos a ambos lados del antimeridiano deben estar dentro")
	}
	if PointInPolygon(Point{0, 0}, poly) {
		t.Fatal("lng 0 está fuera de una banda de 4°")
	}
}

func TestDistanceToSegment(t *testing.T) {
	a, b := Point{0, 0}, Point{0, 1}
	near(t, DistanceToSegmentM(Point{0, 0.5}, a, b), 0, 0.01, "punto sobre el segmento")
	near(t, DistanceToSegmentM(Point{0.01, 0.5}, a, b), 1111.95, 1, "perpendicular a 0.01°")
	near(t, DistanceToSegmentM(Point{0, -0.01}, a, b), 1111.95, 1, "antes de a: clamp a a")
	near(t, DistanceToSegmentM(Point{0, 1.01}, a, b), 1111.95, 1, "después de b: clamp a b")
	near(t, DistanceToSegmentM(Point{0.01, 0}, a, a), 1111.95, 1, "segmento degenerado")
}

func TestDistanceToPolyline(t *testing.T) {
	line := []Point{{0, 0}, {0, 1}, {1, 1}}
	near(t, DistanceToPolylineM(Point{0.5, 1.001}, line), 111.2, 1, "cerca del segundo segmento")
	if d := DistanceToPolylineM(Point{0, 0}, nil); !math.IsInf(d, 1) {
		t.Fatalf("polilínea vacía debe dar +Inf, got %v", d)
	}
	near(t, DistanceToPolylineM(Point{0.01, 0}, []Point{{0, 0}}), 1111.95, 1, "un solo punto")
}
