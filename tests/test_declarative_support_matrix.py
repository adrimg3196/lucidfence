"""Golden test to ensure the unified declarative support matrix matches actual code.

Validates that:
- Min OS versions documented in `declarative-support-matrix.md` match `lucidfence.core.ddm.DDM_MIN_OS`.
- Adapter capabilities mentioned match the actual registry/adapters in `lucidfence/core/adapters/`.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

from lucidfence.core.ddm import DDM_MIN_OS
from lucidfence.core.adapters.jamf import JamfAdapter
from lucidfence.core.adapters.windows_conformidad import WindowsConformidadAdapter


def test_declarative_support_matrix_sync():
    # 1. Read matrix file
    matrix_path = Path("docs/operations/declarative-support-matrix.md")
    assert matrix_path.exists(), "declarative-support-matrix.md must exist in docs/operations/"
    content = matrix_path.read_text(encoding="utf-8")

    # 2. Extract DDM versions from Markdown table
    # Example line: | iOS | Apple DDM | 15.0 | ...
    ddm_versions_found = {}
    pattern = r"\|\s*(iOS|iPadOS|macOS|tvOS|visionOS|watchOS)\s*\|\s*Apple DDM\s*\|\s*([0-9.]+)\s*\|"
    for match in re.finditer(pattern, content, re.IGNORECASE):
        platform, version_str = match.groups()
        parts = tuple(int(x) for x in version_str.split("."))
        ddm_versions_found[platform.lower()] = parts

    # Compare with DDM_MIN_OS
    for platform, min_os in DDM_MIN_OS.items():
        # DDM_MIN_OS keys are: 'ios', 'ipados', 'macos', 'tvos', 'visionos', 'watchos'
        assert platform in ddm_versions_found, f"Platform '{platform}' from DDM_MIN_OS is missing in matrix documentation table"
        assert ddm_versions_found[platform] == min_os, (
            f"Version mismatch for {platform}: "
            f"documented {ddm_versions_found[platform]}, actual code {min_os}"
        )

    # 3. Extract capabilities flags and adapters from Markdown table
    # Example line: | iOS | Apple DDM | 15.0 | ... | `supports_ddm` (Jamf) | ...
    # We want to make sure 'supports_ddm' is associated with Jamf, and 'supports_dsc' with WindowsConformidad (represented in table as Jamf and WindowsConformidad)
    assert "`supports_ddm` (Jamf)" in content, "Jamf support for DDM must be documented as `supports_ddm` (Jamf)"
    assert "`supports_dsc` (WindowsConformidad)" in content, "WindowsConformidad support for DSC must be documented as `supports_dsc` (WindowsConformidad)"

    # Verify real flags on actual adapter classes
    assert getattr(JamfAdapter, "supports_ddm", False) is True, "JamfAdapter should have supports_ddm = True"
    assert getattr(WindowsConformidadAdapter, "supports_dsc", False) is True, "WindowsConformidadAdapter should have supports_dsc = True"
