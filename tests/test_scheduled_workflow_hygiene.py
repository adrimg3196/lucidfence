"""Higiene de los workflows programados: los únicos que escriben al propietario.

GitHub manda un correo al dueño del repo cuando falla un workflow disparado por
`schedule`. Los demás fallan en una PR y se ven en la PR. Por eso los crons son
la superficie que hay que cuidar: cada defecto suyo se convierte en correo.

Este guard fija lo mínimo comprobable, con la causa real detrás de cada regla:

  1. `concurrency` — un cron sin él puede solaparse consigo mismo. `engine-cron`
     corre cada 15 min: dos ciclos a la vez se pelean por la misma rama de datos
     y ambos fallan. Un fallo se convierte en dos.
  2. `timeout-minutes` — sin él, un cuelgue ocupa un runner hasta el límite de
     6 h de GitHub, y el siguiente ciclo se apila detrás. Pero el de JOB cuenta
     también la ESPERA de runner, no solo la ejecución: en una cuenta gratuita
     los runs de `schedule` ya llegan con retraso y la cola pasa de 10 min con
     facilidad. Cuando salta por cola, el job queda `cancelled` y el RUN queda
     `failure` — es decir, correo al propietario por un hipo de infraestructura,
     con cero pasos ejecutados. Ocurrió: run 32734026688 de `engine-cron`, 15
     min en cola, ni un paso, `timeout-minutes: 10` de job. Por eso el límite
     estricto contra cuelgues va a nivel de PASO (que solo corre cuando ya hay
     runner) y el de job se deja holgado como red de seguridad.
  3. Ningún `|| true` sobre `git fetch`/`git ls-remote` — el patrón que motivó
     este fichero: `engine-cron` hacía `git fetch ... || true` y, si el fetch
     fallaba por red, tomaba la rama del `else` y creaba una rama HUÉRFANA cuyo
     push se rechazaba por non-fast-forward. Un parpadeo de red acababa
     disfrazado de problema de historia de git, con un mensaje que no apuntaba
     a la causa. Tragarse el error de una consulta remota y seguir como si nada
     es falso verde con otro nombre.

Lo que este guard NO hace: no opina sobre qué debe comprobar cada cron ni
prohíbe que fallen. Un cron que detecta un problema real DEBE fallar; el correo
entonces está ganado.

Ejecuta: python3 tests/run_tests.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WORKFLOWS = ROOT / ".github" / "workflows"


def _programados() -> list[tuple[str, str]]:
    """[(nombre, texto)] de los workflows con disparador `schedule:`."""
    out = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        texto = p.read_text(encoding="utf-8")
        if re.search(r"^\s*schedule:\s*$", texto, re.M):
            out.append((p.name, texto))
    return out


def test_hay_workflows_programados_que_auditar():
    """Si esto falla, el guard esta mirando al sitio equivocado."""
    assert _programados(), "no se encontro ningun workflow con `schedule:`"


def test_cada_cron_declara_concurrency():
    for nombre, texto in _programados():
        assert re.search(r"^concurrency:", texto, re.M), (
            f"{nombre} es un cron sin `concurrency`: dos ejecuciones pueden "
            f"solaparse y multiplicar el mismo fallo en correos.")


def test_cada_cron_declara_timeout():
    for nombre, texto in _programados():
        assert "timeout-minutes:" in texto, (
            f"{nombre} es un cron sin `timeout-minutes`: un cuelgue ocupa un "
            f"runner hasta el limite de 6 h y apila los ciclos siguientes.")


PISO_TIMEOUT_JOB_MIN = 20


def _timeouts_de_job(texto: str) -> list[int]:
    """`timeout-minutes` a nivel de job (4 espacios), no los de paso (8)."""
    return [int(m) for m in re.findall(r"(?m)^    timeout-minutes: (\d+)\s*$", texto)]


def test_el_timeout_de_job_de_un_cron_no_puede_ser_corto():
    """Un timeout de job corto convierte la cola de runners en correo de fallo.

    `timeout-minutes` de job empieza a contar cuando el job se ENCOLA, no
    cuando arranca. Si el runner tarda mas que el limite, GitHub mata un job
    que no llego a ejecutar un solo paso y el run sale `failure` -> correo.
    El limite util contra cuelgues es el de PASO; este solo es red de
    seguridad, y como tal tiene que ser holgado.
    """
    for nombre, texto in _programados():
        for minutos in _timeouts_de_job(texto):
            assert minutos >= PISO_TIMEOUT_JOB_MIN, (
                f"{nombre}: `timeout-minutes: {minutos}` a nivel de job es "
                f"demasiado corto (minimo {PISO_TIMEOUT_JOB_MIN}). Ese contador "
                f"incluye la espera de runner, asi que una cola larga mata el "
                f"job antes del primer paso y el run sale `failure`, que manda "
                f"correo al propietario. Pon el limite estricto en el paso "
                f"(`timeout-minutes` con 8 espacios) y deja el de job holgado.")


def test_cada_cron_pone_un_limite_estricto_a_nivel_de_paso():
    """Sin timeout de paso, subir el de job dejaria los cuelgues sin guardia.

    Este test es la contrapartida del anterior: si el de job se relaja hasta
    ser holgado, el limite real contra un proceso colgado tiene que existir
    en algun paso. Si no, habriamos cambiado un problema (correo por cola)
    por otro (cuelgue sin cortar).
    """
    for nombre, texto in _programados():
        pasos = re.findall(r"(?m)^        timeout-minutes: (\d+)\s*$", texto)
        assert pasos, (
            f"{nombre}: ningun paso declara `timeout-minutes`. El de job es "
            f"holgado a proposito (incluye la cola de runners), asi que sin "
            f"un limite de paso un proceso colgado se come el runner entero.")


def _disparados_por_pr() -> list[tuple[str, str]]:
    """[(nombre, texto)] de los workflows con disparador `pull_request:`.

    pull_request_target queda fuera a propósito: corre en el contexto de la
    rama base con permisos elevados y su concurrencia tiene otra semántica
    (merge-train ya la declara a su manera).
    """
    out = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        texto = p.read_text(encoding="utf-8")
        if re.search(r"^\s+pull_request:", texto, re.M):
            out.append((p.name, texto))
    return out


def test_cada_workflow_de_pr_cancela_el_run_superado():
    """Un force-push sobre un run de PR en vuelo = correo de fallo sin señal.

    El run superado sigue corriendo contra una ref que ya no existe, muere en
    `failure` y GitHub manda correo al dueño (pasó: gitleaks contra un sha
    huérfano, run 32757168118, cero hallazgos reales). Con `concurrency` +
    `cancel-in-progress` el run superado se CANCELA, y los cancelados no
    generan correo. El correo de fallo debe ser señal, nunca un artefacto de
    la mecánica de git.
    """
    for nombre, texto in _disparados_por_pr():
        assert re.search(r"^concurrency:", texto, re.M), (
            f"{nombre} corre en pull_request sin `concurrency`: un force-push "
            f"deja el run viejo corriendo contra una ref muerta y el fallo "
            f"resultante manda correo al propietario sin decir nada.")
        assert "cancel-in-progress:" in texto, (
            f"{nombre} declara concurrency pero sin `cancel-in-progress`: el "
            f"run superado se encola en vez de cancelarse y puede seguir "
            f"muriendo contra refs que ya no existen.")


def test_ningun_cron_se_traga_el_error_de_una_consulta_remota():
    """`git fetch ... || true` fue el origen de un fallo que mentía sobre su causa."""
    patron = re.compile(r"git\s+(fetch|ls-remote)[^\n|]*\|\|\s*true")
    for nombre, texto in _programados():
        m = patron.search(texto)
        assert not m, (
            f"{nombre}: `{m.group(0).strip()}` se traga el fallo de una consulta "
            f"remota. Distingue 'la rama no existe' de 'no he podido preguntar' "
            f"(git ls-remote --exit-code: RC=2 vs otro) y aborta en el segundo caso.")


def test_los_scripts_que_publican_ramas_de_datos_tampoco_lo_hacen():
    """El mismo patrón vivía duplicado en el script que usa recon-social-cron."""
    patron = re.compile(r"git\s+(fetch|ls-remote)[^\n|]*\|\|\s*true")
    for p in sorted((ROOT / "scripts").glob("*.sh")):
        m = patron.search(p.read_text(encoding="utf-8"))
        assert not m, (
            f"scripts/{p.name}: `{m.group(0).strip()}` se traga el fallo de una "
            f"consulta remota y puede acabar creando una rama huerfana.")
