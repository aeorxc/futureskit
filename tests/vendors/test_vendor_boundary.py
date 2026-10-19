"""The dependency between grammar and vendor spelling runs one way only.

`futureskit.notation` answers what a contract reference means, which is
identically true at any firm using any data vendor. `futureskit.vendors`
answers how one vendor spells it, which is not. Vendor modules may read the
grammar; the grammar must never read a vendor, or the contingent half leaks
back into the invariant half and the split stops meaning anything.
"""

import ast
import pkgutil
from pathlib import Path

import pytest

import futureskit
import futureskit.vendors


def _imported_modules(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_notation_imports_nothing_from_vendors():
    imported = list(_imported_modules(futureskit.notation.__file__))

    assert not [name for name in imported if name.startswith("futureskit.vendors")]


def test_nothing_outside_vendors_imports_a_vendor_module():
    package_root = Path(futureskit.__file__).parent

    offenders = {}
    for path in package_root.rglob("*.py"):
        if "vendors" in path.relative_to(package_root).parts:
            continue
        leaked = [
            name
            for name in _imported_modules(path)
            if name.startswith("futureskit.vendors")
        ]
        if leaked:
            offenders[str(path.relative_to(package_root))] = leaked

    assert offenders == {}


@pytest.mark.parametrize(
    "name",
    [
        "CME_GROUP_EXCHANGES",
        "ONE_DIGIT_YEAR_EXCHANGES",
        "contract_code_from_ric",
        "format_ric_contract",
        "ric_year_digits",
        "tradingview_chart_symbol",
        "tradingview_contract_symbol",
        "tradingview_continuous_symbol",
        "tradingview_overview_symbol",
    ],
)
def test_vendor_spelling_is_not_reachable_from_the_package_root(name):
    # Import it from the vendor module that owns it, so the import line says
    # which vendor a caller depends on.
    assert not hasattr(futureskit, name)
    assert name not in futureskit.__all__
    assert not hasattr(futureskit.notation, name)


def test_every_vendor_module_is_importable():
    found = [
        module.name for module in pkgutil.iter_modules(futureskit.vendors.__path__)
    ]

    assert sorted(found) == ["lseg", "tradingview"]
