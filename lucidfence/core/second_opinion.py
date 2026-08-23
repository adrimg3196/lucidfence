"""Segunda opinión: lo que el UEM AFIRMA frente a lo que se OBSERVA.

El UEM corrige su propio examen. Este informe es la verificación independiente
que piden los auditores: cada discrepancia lleva evidencia de **los dos lados**
y la antigüedad del dato en que se apoya cada uno.

Función pura sobre estado que ya existe: cero llamadas de red, cero escritura,
cero acciones. LucidFence enseña la discrepancia; el admin decide.

Las dos caras de cada control:

  - AFIRMA el UEM: `compliant`, `uem_claimed_encryption` (lo que reportó el
    adaptador, preservado tal cual), `last_checkin`.
  - OBSERVA LucidFence, por canales que el UEM no controla: postura osquery
    (`encryption_enabled` ya resuelta con precedencia de observación,
    `posture_collected_at`), salud de hardware del readback DDM,
    integridad de ubicación (anti-spoofing) y CVE de las apps instaladas.

REGLA DE HONESTIDAD (la misma de todo el producto): una discrepancia solo se
emite cuando **ambos lados son conocidos y se contradicen**. Un lado ausente
(None) nunca genera hallazgo, nunca penaliza y nunca se rellena por inferencia.
"Sin señal suficiente" es una respuesta correcta.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from lucidfence.core.cve import device_cve_summary
from lucidfence.core.policies import _hardware_degraded_components

# El veredicto del UEM se apoya en su último check-in. Si nuestra observación
# independiente es MÁS RECIENTE que el check-in por más de este margen, el
# admin merece saber que está comparando un dato fresco contra uno viejo.
DEFAULT_STALE_CLAIM_AFTER_S = 86400  # 24 h

_SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _parse_ts(raw) -> Optional[datetime]:
    """ISO-8601 -> datetime aware, o None si falta o es ilegible.

    Un timestamp basura deja el dato en "desconocido" (y por tanto sin
    hallazgo); jamás revienta el informe.
    """
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def _age_s(ts: Optional[datetime], now: datetime) -> Optional[float]:
    return None if ts is None else round((now - ts).total_seconds(), 1)


def _finding(dev: dict, control: str, severity: str, why: str,
             claimed, claimed_source: str, claimed_at,
             observed, observed_source: str, observed_at,
             now: datetime, **extra) -> dict:
    claimed_ts, observed_ts = _parse_ts(claimed_at), _parse_ts(observed_at)
    out = {
        "device_id": dev.get("device_id"),
        "name": dev.get("name"),
        "platform": dev.get("platform"),
        "control": control,
        "severity": severity,
        "why": why,
        # Las dos caras, cada una con su procedencia y su antigüedad. Esto es
        # lo que convierte el informe en evidencia y no en una opinión.
        "claimed": {"value": claimed, "source": claimed_source,
                    "at": claimed_at, "age_s": _age_s(claimed_ts, now)},
        "observed": {"value": observed, "source": observed_source,
                     "at": observed_at, "age_s": _age_s(observed_ts, now)},
    }
    out.update(extra)
    return out


def second_opinion_report(devices: list[dict], now: Optional[datetime] = None,
                          stale_claim_after_s: int = DEFAULT_STALE_CLAIM_AFTER_S) -> dict:
    """Discrepancias entre lo que el UEM afirma y lo que se observa.

    `devices` son dicts de DeviceState.to_dict(). Devuelve el informe listo
    para servir por API o pintar en el dashboard.
    """
    now = now or datetime.now(timezone.utc)
    findings: list[dict] = []
    # Dispositivos con al menos un canal independiente disponible: sin esto el
    # denominador mentiría (0 discrepancias sobre una flota que nadie observa
    # no es una buena noticia, es ausencia de señal).
    verifiable = 0

    for dev in devices or []:
        if not isinstance(dev, dict):
            continue
        posture_src = dev.get("posture_source")
        posture_at = dev.get("posture_collected_at")
        checkin_at = dev.get("last_checkin")
        compliant = dev.get("compliant")

        degraded = _hardware_degraded_components(dev.get("hardware_health"))
        integrity = dev.get("location_integrity")
        suspicious = bool(integrity.get("suspicious")) if isinstance(integrity, dict) else None
        has_channel = (bool(posture_src) or bool(degraded) or suspicious is not None
                       or isinstance(dev.get("apps"), list) and bool(dev.get("apps")))
        if has_channel:
            verifiable += 1

        # --- 1. Cifrado: lo que el UEM reportó vs lo que el endpoint enseña ---
        # `uem_claimed_encryption` conserva la afirmación del adaptador;
        # `encryption_enabled` ya trae la observación de osquery cuando existe
        # (la observación gana en el merge del engine, y así debe ser).
        claimed_enc = dev.get("uem_claimed_encryption")
        observed_enc = dev.get("encryption_enabled")
        if posture_src and claimed_enc is not None and observed_enc is not None \
                and claimed_enc != observed_enc:
            if claimed_enc is True:
                findings.append(_finding(
                    dev, "encryption", "critical",
                    "El UEM declara el disco cifrado; la observación directa del "
                    "endpoint dice que no lo está.",
                    True, "uem", checkin_at, False, posture_src, posture_at, now))
            else:
                findings.append(_finding(
                    dev, "encryption", "low",
                    "El endpoint está cifrado pero el UEM aún no lo refleja: su "
                    "inventario va por detrás de la realidad.",
                    False, "uem", checkin_at, True, posture_src, posture_at, now))

        # --- 2. "Compliant" contra salud de hardware degradada (readback DDM) --
        if compliant is True and degraded:
            findings.append(_finding(
                dev, "hardware_health", "high",
                "El UEM da el dispositivo por conforme, pero su propio readback "
                "declara componentes degradados: " + ", ".join(sorted(degraded)) + ".",
                True, "uem", checkin_at, "degraded", "ddm_readback", posture_at, now,
                components=sorted(degraded)))

        # --- 3. "Compliant" contra ubicación no verosímil (anti-spoofing) -----
        if compliant is True and suspicious:
            checks = [c for c in (integrity.get("checks") or []) if isinstance(c, str)]
            findings.append(_finding(
                dev, "location_integrity", "high",
                "El UEM da el dispositivo por conforme; su ubicación reportada no "
                "es verosímil. La conformidad del UEM no dice nada sobre la "
                "autenticidad de la ubicación.",
                True, "uem", checkin_at, "suspicious", "location_integrity",
                dev.get("last_seen"), now, checks=checks))

        # --- 4. "Compliant" contra CVE críticas/altas en apps instaladas ------
        # `apps` tiene que ser una LISTA: un string se iteraría carácter a
        # carácter dentro del sumario de CVE y reventaría el informe entero.
        apps = dev.get("apps")
        if compliant is True and isinstance(apps, list) and apps:
            cve = device_cve_summary([a for a in apps if isinstance(a, dict)])
            if cve["critical_cve_apps"] or cve["high_cve_apps"]:
                sev = "critical" if cve["critical_cve_apps"] else "high"
                findings.append(_finding(
                    dev, "vulnerable_apps", sev,
                    f"El UEM da el dispositivo por conforme con "
                    f"{cve['critical_cve_apps']} app(s) de CVE crítica y "
                    f"{cve['high_cve_apps']} de CVE alta instaladas.",
                    True, "uem", checkin_at,
                    f"{cve['vulnerable_apps']} app(s) vulnerables", "cve_feed",
                    dev.get("last_seen"), now,
                    critical_cve_apps=cve["critical_cve_apps"],
                    high_cve_apps=cve["high_cve_apps"]))

        # --- 5. El veredicto del UEM descansa en un dato más viejo que el nuestro
        checkin_ts, posture_ts = _parse_ts(checkin_at), _parse_ts(posture_at)
        if compliant is not None and checkin_ts and posture_ts:
            lag = (posture_ts - checkin_ts).total_seconds()
            if lag > stale_claim_after_s:
                findings.append(_finding(
                    dev, "stale_claim", "medium",
                    f"El veredicto del UEM se apoya en un check-in "
                    f"{int(lag // 3600)} h más antiguo que la última observación "
                    f"independiente. No es una contradicción, es un dato caducado.",
                    compliant, "uem", checkin_at,
                    "observación más reciente", posture_src or "lucidfence",
                    posture_at, now, lag_s=round(lag, 1)))

    findings.sort(key=lambda f: (-_SEV_ORDER.get(f["severity"], 0),
                                 str(f.get("device_id") or "")))
    by_control: dict[str, int] = {}
    for f in findings:
        by_control[f["control"]] = by_control.get(f["control"], 0) + 1

    return {
        "generated_at": now.isoformat(),
        "devices_total": len([d for d in (devices or []) if isinstance(d, dict)]),
        # Sin canal independiente no hay segunda opinión posible: decirlo evita
        # leer "0 discrepancias" como "todo correcto".
        "devices_verifiable": verifiable,
        "discrepancies_total": len(findings),
        "by_control": by_control,
        "discrepancies": findings,
        "stale_claim_after_s": stale_claim_after_s,
    }
