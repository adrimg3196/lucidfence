"""Live end-to-end test of Atomic Mail Agentic integration (REAL email).

Registers a fresh @atomicmail.ai inbox via proof-of-work and sends a real email
to a configurable recipient. Requires:
  - python3.11+ (hashlib.scrypt for PoW)
  - network access to auth.atomicmail.ai / api.atomicmail.ai

Skipped automatically if those conditions are not met. Set ATOMICMAIL_TEST_TO
to a real address you can check to verify deliverability.

Run with: python3.11 -m pytest tests/test_atomicmail_live.py -s
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HAS_SCRYPT = hasattr(__import__("hashlib"), "scrypt")


@unittest.skipUnless(HAS_SCRYPT, "hashlib.scrypt requerido (usa python3.11+)")
class AtomicMailLiveTest(unittest.TestCase):
    def test_register_and_send_real(self):
        import concurrent.futures as cf
        import random
        import string
        from core.atomicmail_client import TenantMailbox

        to = os.environ.get("ATOMICMAIL_TEST_TO", "")
        # Use a non-routable but valid-looking target if none provided so the
        # JMAP submission is still exercised without spamming a real inbox.
        to = to or "lf-live-test@atomicmail.ai"

        def run():
            td = tempfile.mkdtemp(prefix="lf-live-")
            uname = "lf-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            mb = TenantMailbox(tenant_dir=td, username=uname)
            self.assertTrue(mb.ensure_registered(), mb.status())
            self.assertIsNotNone(mb._inbox_id)
            ok = mb.send(
                to=to,
                subject="[LucidFence] PRUEBA live Atomic Mail",
                text="Mensaje de prueba enviado por LucidFence via Atomic Mail Agentic (JMAP).",
            )
            return ok, mb._inbox_id, mb.status()

        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            try:
                ok, inbox, status = ex.submit(run).result(timeout=90)
            except cf.TimeoutError:
                self.fail("timeout: el envio real colgado (debe tener timeout)")
        self.assertTrue(ok, status)
        print(f"\n[live] inbox={inbox} -> {to} enviado OK")


if __name__ == "__main__":
    unittest.main(verbosity=2)
