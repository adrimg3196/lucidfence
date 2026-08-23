# Segunda opinión: lo que el UEM afirma vs lo que se observa

`GET /api/second-opinion` · módulo `lucidfence/core/second_opinion.py`

El UEM corrige su propio examen. Cuando Intune dice «este equipo cumple» o Jamf
dice «disco cifrado», lo dice basándose en lo que su propio agente le reportó, y
en la fecha en que se lo reportó. Un auditor no acepta eso: pide verificación
independiente.

Este informe es esa verificación. Cada discrepancia trae evidencia de **los dos
lados** y la **antigüedad** del dato en que se apoya cada uno.

## Por qué esto solo lo puede hacer un complemento neutral

Microsoft no va a auditar a Jamf, ni Jamf a Intune, ni ninguno a sí mismo. El
overlay neutral es el único que puede contrastar la afirmación del UEM contra
señales que el UEM no controla. No sustituimos al UEM: le tomamos la lección.

## Las dos caras

| Afirma el UEM | Observa LucidFence (canales que el UEM no controla) |
| --- | --- |
| `compliant` | postura osquery (cifrado real del disco) |
| `uem_claimed_encryption` | readback DDM de salud de hardware |
| `last_checkin` (la fecha de su verdad) | integridad de ubicación (anti-spoofing) |
| | CVE de las apps instaladas |

## Qué detecta

| Control | Discrepancia | Severidad |
| --- | --- | --- |
| `encryption` | El UEM declara el disco cifrado; el endpoint observado dice que no | **crítica** |
| `encryption` | El endpoint está cifrado y el UEM aún no se ha enterado | baja |
| `hardware_health` | «Conforme» con componentes degradados en su propio readback | alta |
| `location_integrity` | «Conforme» con una ubicación que no es verosímil | alta |
| `vulnerable_apps` | «Conforme» con apps de CVE crítica/alta instaladas | crítica/alta |
| `stale_claim` | Su veredicto se apoya en un check-in más viejo que nuestra observación | media |

## La regla de honestidad

**Una discrepancia solo se emite cuando los dos lados son conocidos y se
contradicen.** Un lado ausente (`None`) nunca genera hallazgo, nunca penaliza y
nunca se rellena por inferencia.

Esto no es una limitación: es lo que hace que el panel sea creíble. Si lo
desconocido pudiera delatar, el informe se llenaría de ruido y el admin dejaría
de mirarlo — que es exactamente cómo mueren los paneles de cumplimiento.

Por eso el informe publica `devices_verifiable` junto a `devices_total`: **cero
discrepancias sobre una flota que nadie observa no es una buena noticia, es
ausencia de señal**, y el número lo dice en voz alta.

## Lo que este informe NO hace

- **No ejecuta nada.** Ni bloquea, ni pone en cuarentena, ni avisa al usuario.
  Enseña la discrepancia; el admin decide. Frontera inviolable del producto.
- **No certifica cumplimiento.** Es evidencia para un auditor, no un sello.
- **No sale a la red.** Función pura sobre estado que ya está en local.

## Uso

```sh
curl -s localhost:8765/api/second-opinion | python3 -m json.tool
# el margen del check-in caducado es ajustable (60..2592000 s; por defecto 24 h)
curl -s "localhost:8765/api/second-opinion?stale_claim_after_s=3600"
```

Permiso `device:read`, acotado al tenant, igual que `/api/coverage`.

### Forma de un hallazgo

```json
{
  "device_id": "d1",
  "control": "encryption",
  "severity": "critical",
  "why": "El UEM declara el disco cifrado; la observación directa del endpoint dice que no lo está.",
  "claimed":  {"value": true,  "source": "uem",     "at": "...", "age_s": 600.0},
  "observed": {"value": false, "source": "osquery", "at": "...", "age_s": 300.0}
}
```

## Nota de implementación: por qué antes esto era imposible

La postura observada por osquery **sobrescribía** el campo `encryption_enabled`
que venía del UEM. La observación debe ganar —es evidencia directa—, pero al
ganar borraba la afirmación del UEM y con ella la contradicción: el estado final
decía «sin cifrar» y nadie podía ya saber que el UEM había afirmado lo
contrario.

`DeviceState.uem_claimed_encryption` conserva la afirmación intacta. La
observación sigue ganando donde debe; las dos caras sobreviven.

## Verificación

- `tests/test_second_opinion.py` — la regla de honestidad primero.
- `scripts/runtime_validation.py` — dispositivo mentiroso inyectado en el estado
  real del engine: delatado con ambas caras; y el mismo caso sin observación
  independiente, callado.
