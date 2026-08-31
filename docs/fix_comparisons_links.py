#!/usr/bin/env python3
"""Fix broken doc links in comparisons/*.md"""
import os, re

def fix_file(filepath):
    with open(filepath) as f:
        content = f.read()
    
    # Desde docs/comparisons/:
    # "../integrations/X" -> docs/integrations/X  (CORRECTO, existe)
    # "../../integrations/X" -> root/integrations/X (MAL, no existe)
    #   -> corregir a "../integrations/X"
    content = content.replace('](../../integrations/', '](../integrations/')
    
    # "../lucidfence/core/X" -> docs/lucidfence/core/X (MAL, no existe)
    # "../../lucidfence/core/X" -> root/lucidfence/core/X (CORRECTO, existe)
    #   -> corregir "../lucidfence/core/X" -> "../../lucidfence/core/X"
    content = content.replace('](../lucidfence/core/', '](../../lucidfence/core/')
    
    # "../operations/X" -> docs/operations/X (CORRECTO)
    # "../../operations/X" -> root/operations/X (MAL)
    content = content.replace('](../../operations/', '](../operations/')
    
    # "../reference/X" -> docs/reference/X (CORRECTO)
    # "../../reference/X" -> root/reference/X (MAL)
    content = content.replace('](../../reference/', '](../reference/')
    
    # "../architecture/X" -> docs/architecture/X (CORRECTO)
    # "../../architecture/X" -> root/architecture/X (MAL)
    content = content.replace('](../../architecture/', '](../architecture/')
    
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath

for f in [
    'docs/comparisons/lucidfence-vs-intune.md',
    'docs/comparisons/lucidfence-vs-jamf.md',
]:
    print(f"Fixed: {fix_file(f)}")
print("Done.")
