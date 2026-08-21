# DESIGN.md — el mundo visual de LucidFence

Decisiones visuales duraderas. Lo que aquí está escrito manda sobre el gusto de
quien toque el código después. Los tokens viven en `../static/design.css` (fuente
única) y `tests/test_design_system_single_source.py` impide que esto vuelva a
divergir.

## Qué es este producto, visualmente

Un panel de operación para un admin de IT que mira flota, riesgo y evidencia
durante horas, normalmente en una oficina iluminada y a menudo con otra
herramienta al lado. **Modo Operate**: la herramienta desaparece dentro de la
tarea. La marca no se grita, se nota en la precisión de los detalles.

## El mundo: "perímetro sereno"

- **Papel cálido en claro, carbón cálido en oscuro.** El claro es el defecto
  porque el uso real es diurno y en interior, no porque el oscuro se vea mejor
  en una captura.
- **Un solo acento: verde valla `#3E7A5E`.** Marca acción primaria, selección
  actual e indicador de estado. Nunca decora.
- **El color semántico solo informa** (dentro / fuera / aviso / incumple).
  Cinco tonos, cada uno con su superficie tenida, todos legibles sobre ella.
- **La firma es una línea, no un logo grande:** 2px de verde continuo bajo la
  cabecera = perímetro íntegro; cada muesca ámbar es un aviso abierto.

## Tipografía

**IBM Plex Sans**, autoalojada desde `/static/fonts` (SIL OFL 1.1, subconjunto
Latin1, 4 pesos, 86 KB). Una sola cara para toda la interfaz.

Por qué esta y no otra: Plex está dibujada para paneles densos y trae cifras
tabulares de verdad. Inter, Geist y Roboto —las tres que este repo tenía
repartidas— son exactamente las caras a las que converge cada ola de interfaces
generadas; usarlas es no haber decidido.

- **Sin pareja display + body.** En un panel de operación eso añade ruido, no
  jerarquía. La jerarquía la dan tamaño y peso.
- **Rampa fija en px**, no fluida: el admin mira a DPI constante y un titular
  que encoge dentro de un panel se ve peor, no mejor. `11 · 12 · 13 · 15 · 18 ·
  24 · 30`. El defecto de la interfaz es 13px.
- **11px es el suelo.** Por debajo, el texto funcional deja de leerse en
  pantallas densas. No hay excepción "es solo una etiqueta".
- **La monoespaciada es para código, identificadores y hashes.** Usarla como
  disfraz de "técnico" en etiquetas o datos es un tic; las cifras se alinean
  con `tabular-nums`.

## Color y contraste

Todo texto pasa **AA 4.5:1 sobre cada superficie en la que se dibuja**, en claro
y en oscuro. No es una aspiración: se calcula en el test, no se estima a ojo.

El texto sobre el acento usa `--accent-fg`, nunca `#fff` fijo: en tema oscuro el
acento es un verde claro y el blanco se cae a 2.6:1.

## Elevación

**Se declara una vez: borde o sombra, nunca las dos.**

- En reposo (tarjetas, filas, paneles): borde de 1px, sin sombra.
- Elevado (modal, paleta de comandos, toast, menú): sombra, sin borde.

Un borde fino bajo una sombra ancha es el "ghost card". Toda sombra lleva
desplazamiento y desenfoque; un halo de color a offset cero es decoración, no
profundidad.

## Movimiento

150–250 ms, y solo para comunicar estado: cambio, respuesta, carga, aparición.
El admin está dentro de una tarea, no viendo una coreografía. Nada de secuencias
al cargar la página.

## Lo que no entra

Cada una de estas estaba en el código antes de esta pasada. El guard las
mantiene fuera.

- **Franja de color al costado** (`border-left: 3px`) en tarjetas, filas o
  avisos. La severidad se lee en un punto guía y la superficie tenida.
- **Micro-etiqueta en versal encima de un encabezado.** El encabezado ya dice
  lo que ella repite. Si la información importa, va dentro del encabezado o en
  una fila de estado debajo.
- **Degradados decorativos** y texto con degradado. El énfasis es peso o tamaño.
- **Halos de color** alrededor de logos y tarjetas.
- **Glifos Unicode como iconos** (`✓`, `→`). Los iconos se dibujan: `reicon` en
  el dashboard, SVG propio fuera. Además caen fuera del subconjunto Latin1 y
  saltarían a otra cara.
- **Retículas de líneas como fondo**, salvo bajo un mapa o un lienzo real (la
  PWA la usa bajo el mapa, y ahí sí está ganada).
- **Una cuarta identidad.** Landing, cloud, manual, PWA y whitelabel visten el
  tema oscuro del producto. Antes la landing vendía LucidFence en índigo y la
  PWA en violeta: el cliente veía tres empresas.

## Superficies del navegador

Lo que no dibujamos también es diseño. Selección, cursor de texto, barra de
scroll, anillo de foco y `::placeholder` se tiñen de la paleta en `design.css`.
Es la señal más barata de que una página se construyó en vez de ensamblarse, y
la que más se olvida.

## Cómo verificar

```sh
python3 tests/run_tests.py            # incluye el guard del sistema de diseño
node .claude/skills/impeccable/scripts/detect.mjs static/*.html
```

El detector de Impeccable deja cinco hallazgos vivos a propósito; el porqué de
cada uno está escrito en `test_known_detector_deviations_are_documented`, y ese
test falla si alguien borra la explicación sin borrar la causa.
