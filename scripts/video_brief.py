#!/usr/bin/env python3
"""Genera un brief/guion de video para LucidFence combinando:
- recon de competidores (scripts/recon_repos.py)
- estructura ganadora de anuncios UEM/MDM (hook -> que es -> diferenciador ->
  beneficios -> CTA) extraida de Applivery/Jamf/Kandji/Hexnode.
Inspirado en contents-maker (trend tracker) y video-script-generator (guion
estructurado), pero en codigo propio minimo del repo.
Salida: brand/brief_<ts>.json listo para pasar al CinematicRenderer.
Uso: python3 scripts/video_brief.py [--topic lucidfence]"""
import json, subprocess, sys, os, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEF = {
    "product": "LucidFence",
    "tagline": "El perimetro que piensa.",
    "structure": "hook -> what -> differentiator -> benefits -> cta",
    "scenes": [
        {"beat": "hook", "line": "Tu flota se mueve.", "visual": "dash_resumen",
         "why": "Competidores (Applivery/Hexnode) abren con dispositivos en movimiento."},
        {"beat": "what", "line": "Multi-UEM: Apple, Android, Windows.", "visual": "dash_dispositivos",
         "why": "Promesa multiplataforma es central en todo el sector UEM/MDM."},
        {"beat": "differentiator", "line": "Si sale de tu zona, LucidFence la aisla.", "visual": "dash_soar",
         "why": "Ningun competidor aisla por geolocalizacion ni responde a CVEs/intrusos. Este es el giro."},
        {"beat": "benefits", "line": "Compliance + CVEs en vivo + SOAR.", "visual": "dash_geovallas",
         "why": "Kandji pone Compliance central; nosotros lo llevamos a proactivo (CVEs+SOAR)."},
        {"beat": "cta", "line": "Define el perimetro. El resto, solo. LucidFence.", "visual": "dash_resumen",
         "why": "Cierre de marca pegajoso tipo 'So I Do That with Kandji'."},
    ],
}

def run_recon():
    """Llama al recon de competidores y devuelve las lineas relevantes."""
    try:
        out = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "recon_repos.py")],
                             capture_output=True, text=True, timeout=30)
        return out.stdout
    except Exception as e:
        return f"(recon no disponible: {e})"

def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    recon = run_recon()
    brief = dict(BRIEF)
    brief["recon_excerpt"] = "\n".join(recon.splitlines()[:12])
    brief["generated_at"] = ts
    out_path = os.path.join(REPO, "brand", f"brief_{ts}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
    print(f"Brief generado: {out_path}")
    print(f"Escenas: {len(brief['scenes'])} | Producto: {brief['product']}")
    print("Estructura:", brief["structure"])

if __name__ == "__main__":
    main()
