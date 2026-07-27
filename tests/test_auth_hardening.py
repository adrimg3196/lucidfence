"""Auth hardening: lockout de fuerza bruta, timing uniforme y purga de sesiones.

superpowers:test-driven-development — escritos ANTES de la implementación.
"""
import os
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from saas.auth import AuthStore  # noqa: E402


def _store():
    root = Path(tempfile.mkdtemp(prefix="lf_auth_"))
    return AuthStore(root)


def test_lockout_after_repeated_failures():
    """5 fallos seguidos bloquean el login aunque la 6a password sea correcta."""
    st = _store()
    st.create_user("a@b.com", "A", "correcthorse1", "org_1")
    for _ in range(5):
        assert st.authenticate("a@b.com", "wrong-pass") is None
    # aun con la password buena, dentro de la ventana debe estar bloqueado
    assert st.authenticate("a@b.com", "correcthorse1") is None


def test_lockout_window_drains():
    """Pasada la ventana, el usuario puede volver a entrar."""
    os.environ["LUCIDFENCE_LOGIN_WINDOW_S"] = "1"
    try:
        st = _store()
        st.create_user("c@d.com", "C", "correcthorse1", "org_1")
        for _ in range(5):
            st.authenticate("c@d.com", "nope")
        time.sleep(1.2)
        u = st.authenticate("c@d.com", "correcthorse1")
        assert u is not None and u.email == "c@d.com"
    finally:
        os.environ.pop("LUCIDFENCE_LOGIN_WINDOW_S", None)


def test_success_clears_failures():
    st = _store()
    st.create_user("e@f.com", "E", "correcthorse1", "org_1")
    for _ in range(3):
        st.authenticate("e@f.com", "nope")
    assert st.authenticate("e@f.com", "correcthorse1") is not None
    # el contador quedo limpio: 4 fallos nuevos aun no bloquean
    for _ in range(4):
        st.authenticate("e@f.com", "nope")
    assert st.authenticate("e@f.com", "correcthorse1") is not None


def test_unknown_email_burns_kdf_time():
    """Email inexistente debe costar ~lo mismo que uno existente (anti-enumeracion)."""
    st = _store()
    st.create_user("g@h.com", "G", "correcthorse1", "org_1")
    t0 = time.perf_counter()
    st.authenticate("g@h.com", "wrongpassword")
    known = time.perf_counter() - t0
    t0 = time.perf_counter()
    st.authenticate("nobody@nowhere.com", "wrongpassword")
    unknown = time.perf_counter() - t0
    # el camino 'desconocido' no puede ser despreciable frente al conocido
    assert unknown >= known * 0.3, f"timing oracle: known={known:.4f}s unknown={unknown:.4f}s"


def test_purge_expired_sessions():
    st = _store()
    u = st.create_user("i@j.com", "I", "correcthorse1", "org_1")
    tok = st.create_session(u.id)
    # caducar a mano
    st._sessions[tok]["expires_at"] = time.time() - 10
    removed = st.purge_expired_sessions()
    assert removed >= 1
    assert st.get_session(tok) is None
    assert tok not in st._sessions


def test_create_session_purges_opportunistically():
    st = _store()
    u = st.create_user("k@l.com", "K", "correcthorse1", "org_1")
    stale = st.create_session(u.id)
    st._sessions[stale]["expires_at"] = time.time() - 10
    st.create_session(u.id)  # debe purgar la caducada de paso
    assert stale not in st._sessions
