#!/usr/bin/env python3
"""Genera y ejecuta los daily prompts de todos los agentes de LucidFence."""
import subprocess, os, datetime, re

today = datetime.date.today().isoformat()
output_dir = f'/Users/adri/lucidfence/data/dailies/{today}'
os.makedirs(output_dir, exist_ok=True)

profiles = [
    ('ceo', 'CEO'),
    ('cto', 'CTO'),
    ('finance', 'Finance'),
    ('marketing', 'Marketing'),
    ('product', 'Product'),
    ('selfimprove', 'Self-Improve'),
]

for profile, label in profiles:
    prompt_file = f'/Users/adri/.hermes/scripts/{profile}_daily_prompt.py'
    if not os.path.exists(prompt_file):
        print(f'[{label}] SIN SCRIPT')
        continue

    with open(prompt_file) as f:
        content = f.read()
        match = re.search(r'prompt\s*=\s*"""(.*?)"""', content, re.DOTALL)
        if match:
            prompt_text = match.group(1)
        else:
            prompt_text = content

    print(f'[{label}] Prompt ({len(prompt_text)} chars) — listo')
    with open(f'{output_dir}/{profile}_prompt.txt', 'w') as f:
        f.write(prompt_text)

print(f'\n✅ {len(profiles)} prompts listos en {output_dir}')
