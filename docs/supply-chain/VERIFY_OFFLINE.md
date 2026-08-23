# Verificación offline de procedencia y SBOM (LucidFence #233)

Este documento explica cómo cualquier administrador puede **verificar la
procedencia de un release de LucidFence sin red, sin cuentas cloud y sin
dependencias de pago**. Solo hace falta Python 3.11 (el intérprete del propio
LucidFence) y los scripts del repo.

> Claim soportado: **"provenance verificable, 100% free, /bin/bash"**.
> Por diseño NO afirmamos "firmado por LucidFence" (no hay CA nuestra): el
> artefacto está **firmado por el operador que hizo el release** y es
> **verificable por hash** de extremo a extremo.

------------------------------------------------------------------
## Qué se entrega en cada release
------------------------------------------------------------------

Junto al artefacto (`*.tar.gz` / `*.whl`) se publican dos ficheros:

| Fichero                  | Qué es                                                        |
|--------------------------|--------------------------------------------------------------|
| `sbom.cdx.json`          | SBOM CycloneDX 1.5 determinista (componentes + hash de cada fichero fuente) |
| `provenance.dsse.json`   | Envelope DSSE que envuelve un *in-toto Statement* firmado    |

El envelope DSSE tiene este shape (sin dependencias de `in-toto`/`cosign`):

```json
{
  "payloadType": "application/vnd.in-toto+json",
  "payload": "<base64 del in-toto Statement (JSON canónico)>",
  "signatures": [
    { "keyid": "<sha256 de la clave pública del operador>",
      "sig": "<base64 de la firma Ed25519 sobre los bytes del payload>" }
  ]
}
```

El *in-toto Statement* declara:

- `subject[].digest.sha256` = hash del artefacto de release.
- `predicateType` = `https://lucidfence.io/provenance/release/v1`
- `predicate` = `{ builder, buildType, invocation.configSource.commit,
  metadata, version, sbom{sha256,format}, gate }`

------------------------------------------------------------------
## Verificación mínima (stdlib, sin red)
------------------------------------------------------------------

El núcleo del verificador **no importa `cryptography`** salvo que pases
`--key`. Detecta alteración solo con `hashlib` + `json` + `git`:

1. `artifact_intact`   — sha256(artefacto) == subject.digest.sha256
2. `sbom_intact`       — sha256(sbom) == predicate.sbom.sha256
3. `commit_linked`     — el commit del predicate es ancestro de HEAD (`git merge-base --is-ancestor`)
4. `version_consistent`— predicate.version == pyproject == .release-version
5. `signature_optional`— si `--key`: verifica Ed25519; si no: avisa "unverified" pero NO falla
6. `canonical_stable`  — re-serializar canónicamente reproduce el mismo digest

### Comando copia-pega (offline)

```bash
# Desde la raíz del repo clonado:
python3.11 scripts/verify_provenance.py \
    --artifact dist/lucidfence-1.6.0.tar.gz \
    --sbom     sbom.cdx.json \
    --dsse     provenance.dsse.json \
    --repo     . \
    --json
```

Salida esperada: `VERIFY PROVENANCE: APTO` y exit 0. Cualquier alteración
del artefacto, del SBOM o de la cadena de commits produce `FALLO` (exit 1).

### Comprobar también la firma del operador (opcional)

```bash
# Requiere la clave PÚBLICA Ed25519 del operador (fuera del repo, la da quien hizo el release)
python3.11 scripts/verify_provenance.py \
    --artifact dist/lucidfence-1.6.0.tar.gz \
    --sbom     sbom.cdx.json \
    --dsse     provenance.dsse.json \
    --repo     . \
    --key      /ruta/a/release_signing.pub
```

Sin `--key` la verificación de hashes sigue cubriendo la *integridad*; la
clave añade *autenticidad* (sabes qué operador firmó).

------------------------------------------------------------------
## Fixture de ejemplo (en el repo, verificable sin red)
------------------------------------------------------------------

Para que cualquiera pueda probar el verificador sin hacer un release, el repo
incluye una fixture bajo `docs/supply-chain/fixture/`:

```
docs/supply-chain/fixture/
├── lucidfence-1.6.0.tar.gz          # artefacto de ejemplo
├── sbom.cdx.json                    # SBOM CycloneDX 1.5 (versión 1.6.0)
├── provenance.dsse.json            # envelope DSSE firmado
└── release_signing_demo.pub        # clave PÚBLICA de DEMO (solo para este doc)
```

> La clave `release_signing_demo.pub` es de **demo**, generada solo para este
> documento. En producción usa tu propia clave Ed25519; la privada NUNCA se
> commitea (está en tu HSM/disco, fuera del repo).

### Verificar la fixture (esto es lo que corre `python3 scripts/verify.py`)

```bash
python3.11 scripts/verify_provenance.py \
    --artifact docs/supply-chain/fixture/lucidfence-1.6.0.tar.gz \
    --sbom     docs/supply-chain/fixture/sbom.cdx.json \
    --dsse     docs/supply-chain/fixture/provenance.dsse.json \
    --repo     . \
    --key      docs/supply-chain/fixture/release_signing_demo.pub \
    --json
# => VERIFY PROVENANCE: APTO
```

------------------------------------------------------------------
## Generar tú mismo la procedencia de un release
------------------------------------------------------------------

```bash
# 1) Empaqueta el artefacto (ejemplo: sdist)
python3.11 -m build --sdist            # ó tu pipeline de build

# 2) Genera el SBOM (lee la versión de pyproject.toml, nunca hardcodeada)
python3.11 scripts/generate_sbom.py --out sbom.cdx.json

# 3) Firma con tu clave Ed25519 (operador, fuera del repo)
#    openssl pkey -in release_signing.key -out release_signing.pub -pubout
python3.11 scripts/provenance_attest.py \
    --artifact dist/lucidfence-1.6.0.tar.gz \
    --sbom     sbom.cdx.json \
    --key      /ruta/a/release_signing.key \
    --out      provenance.dsse.json \
    --repo     .

# 4) (Opcional) añade una firma Sigstore transparente SI cosign está en PATH
python3.11 scripts/provenance_attest.py ... --sigstore
#    Si cosign NO está, el release continúa igual. Sigstore nunca es obligatorio.

# 5) Publica artefacto + sbom.cdx.json + provenance.dsse.json juntos.
```

------------------------------------------------------------------
## Gate de release (bloquea divergencia)
------------------------------------------------------------------

Antes de `git tag` / `fly deploy` / `twine upload`, el pipeline corre
`scripts/release_preflight.py` en modo release. Si falta el SBOM o la
attestation, o si el hash del artefacto / commit / versión no cuadra, el
verdict es **DO NOT RELEASE** (exit 1):

```bash
python3.11 scripts/release_preflight.py --artifact dist/lucidfence-1.6.0.tar.gz
#   [PASS] sbom_present
#   [PASS] provenance_present
#   [PASS] prov_artifact_match
#   [PASS] prov_commit_ancestor
#   [PASS] prov_version_match
# VERDICT: READY TO RELEASE
```

Y `python3 scripts/verify.py` (el "único punto de hecho") incluye ahora el
check **"Provenance release"**, que verifica la fixture del repo offline.

------------------------------------------------------------------
## Reproducibilidad del payload (AC2)
------------------------------------------------------------------

El payload del DSSE se serializa con JSON **canónico**:

```python
json.dumps(statement, sort_keys=True, separators=(",", ":"))
```

Los campos volátiles (`metadata.buildStartedOn`) se excluyen del cálculo del
digest. Por tanto, ejecutar el productor dos veces sobre la misma entrada
produce un payload base64 **idéntico** (mismo sha256). Puedes comprobarlo:

```bash
A=$(python3.11 scripts/provenance_attest.py --artifact x --sbom y --key k --out /tmp/1.json ... && \
     python3 -c "import base64,json;print(base64.b64decode(json.load(open('/tmp/1.json'))['payload']).hex())")
B=$(python3.11 scripts/provenance_attest.py --artifact x --sbom y --key k --out /tmp/2.json ... && \
     python3 -c "import base64,json;print(base64.b64decode(json.load(open('/tmp/2.json'))['payload']).hex())")
[ "$A" = "$B" ] && echo "DETERMINISTA" || echo "DIVERGENTE"
```

------------------------------------------------------------------
## No-objetivos (qué NO prometemos)
------------------------------------------------------------------

- **No** reproducibilidad bit-a-bit del build (`metadata.reproducible=false`).
- **No** exigimos cuenta cloud ni clave de LucidFence (clave del operador).
- **No** usamos `slsa-verifier` ni el paquete PyPI `in-toto`/`cosign`.
- La firma es **opcional**: la integridad siempre se cubre con hashes.
