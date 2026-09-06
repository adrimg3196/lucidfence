# LucidFence

**Geofencing multi-UEM local-first, gratis y open source (Apache-2.0).** Motor de
riesgo explicable sobre los UEM que ya tienes (Applivery, Intune, Jamf, Fleet,
Workspace ONE). Tu dato de ubicación no sale de tu máquina.

> **Estado: LucidFence 2.0 en construcción.** `main` contiene la reescritura en
> Go. Última pre-release: **2.0.0-alpha.1** (núcleo demo, hito M1), en
> [GitHub Releases](https://github.com/adrimg3196/lucidfence/releases). La última
> versión estable sigue siendo **1.6.1** (Python): código en la rama
> [`legacy/python`](https://github.com/adrimg3196/lucidfence/tree/legacy/python)
> y tag `v1.6.1-python-final`. Homebrew, Docker y la vitrina siguen sirviendo 1.6.1
> hasta la release 2.0.0.

## Por qué 2.0

Un binario en Go, sin runtime que instalar; dashboard React embebido; el
repositorio contiene solo producto. Diseño completo en
`docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md`;
arquitectura normativa en `ARCHITECTURE.md`.

## Desarrollo

```bash
brew install go golangci-lint      # Go 1.27+
make web                            # compila el dashboard (Node 24+)
make build && ./bin/lucidfence version
make verify                         # el gate completo: lint, tests, cobertura, web, batería
```

## Principios

Local-first y cero telemetría · complemento del UEM, nunca un UEM · el admin
decide el runtime (`observe` por defecto, doble llave para `wipe`) · gratis y
open source · todo claim verificado en vivo.

## Licencia

Apache-2.0. Ver `LICENSE`.
