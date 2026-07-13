import sys, os
sys.path.insert(0, os.path.realpath('.'))
from core.policies import RiskEngine, load_policies
from pathlib import Path

re = RiskEngine()
pols = load_policies(Path('data/policies.json'))
print("policies cargadas:", len(pols))

# Caso 1: fuera de geocerca, fuera de turno, turno conocido -> debe disparar pol-offshift-outside
dev = {"device_id":"d1","compliant":True,"rooted":False,"encryption_enabled":True,"os_outdated":False,"fence_id":None}
ctx = {"hour":22,"shift_zones":{"d1":"warehouse_A"},"zone_risk":{}}
risk = re.evaluate(dev,"outside",ctx)
fired = re.match_policies(pols, risk, dev, "outside")
print("\n[Caso 1] outside + offshift")
print("  risk:", risk["risk_score"], risk["severity"])
print("  policies:", [f["policy_id"] for f in fired])
assert any(f["policy_id"]=="pol-offshift-outside" for f in fired), "FALLO: deberia disparar offshift"

# Caso 2: rooteado + outside -> critico
dev2 = {"device_id":"d2","compliant":False,"rooted":True,"encryption_enabled":True,"os_outdated":False,"fence_id":None}
risk2 = re.evaluate(dev2,"outside",ctx)
fired2 = re.match_policies(pols, risk2, dev2, "outside")
print("\n[Caso 2] rooted + outside")
print("  risk:", risk2["risk_score"], risk2["severity"])
print("  policies:", [f["policy_id"] for f in fired2])
assert any(f["policy_id"]=="pol-rooted-outside" for f in fired2), "FALLO: deberia disparar rooted"

# Caso 3: dentro de geocerca, conforme, turno correcto -> sin politicas
dev3 = {"device_id":"d3","compliant":True,"rooted":False,"encryption_enabled":True,"os_outdated":False,"fence_id":"warehouse_A"}
ctx3 = {"hour":10,"shift_zones":{"d3":"warehouse_A"},"zone_risk":{}}
risk3 = re.evaluate(dev3,"inside",ctx3)
fired3 = re.match_policies(pols, risk3, dev3, "inside")
print("\n[Caso 3] inside + compliant + onshift")
print("  risk:", risk3["risk_score"], risk3["severity"])
print("  policies:", [f["policy_id"] for f in fired3])
assert not fired3, "FALLO: no deberia disparar nada"

print("\nTODO OK ✓  (motor de riesgo/politicas compuesto funcional)")
