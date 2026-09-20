from __future__ import annotations

import hashlib
import importlib.util
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from tools.custom import CUSTOM_TOOL_SPEC

logger = logging.getLogger(__name__)
SERVICE_ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class CustomToolLoadReport:
    directory: str
    modules: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_custom_tools(
    registry: Any,
    directory: str | Path,
    *,
    enabled: bool = True,
    strict: bool = False,
    modules: list[str] | None = None,
) -> CustomToolLoadReport:
    """Load trusted developer modules from one bounded local directory.

    Only direct ``*.py`` files (or explicitly named direct files) are loaded;
    arbitrary paths, packages outside the configured directory and remote
    source are intentionally unsupported.
    """

    root = _resolve_directory(directory)
    report = CustomToolLoadReport(directory=str(root))
    if not enabled or not root.is_dir():
        return report

    candidates = _module_candidates(root, modules)
    for path in candidates:
        module_name = _module_name(path)
        try:
            module = _load_module(module_name, path)
            _register_module(registry, module, report)
            report.modules.append(path.name)
        except Exception as exc:
            message = f"{path.name}: {str(exc)[:500] or 'load failed'}"
            report.errors.append(message)
            logger.exception("custom tool module failed to load: %s", path)
            sys.modules.pop(module_name, None)

    if strict and report.errors:
        raise RuntimeError("Custom tool loading failed: " + "; ".join(report.errors))
    return report


def _resolve_directory(directory: str | Path) -> Path:
    raw = Path(str(directory or "custom_tools"))
    return (raw if raw.is_absolute() else SERVICE_ROOT / raw).resolve()


def _module_candidates(root: Path, modules: list[str] | None) -> list[Path]:
    if modules:
        candidates: list[Path] = []
        for raw in modules:
            name = str(raw).strip()
            if not name or Path(name).name != name:
                raise ValueError(
                    f"Custom tool module must be a direct file name: {name}"
                )
            path = (root / (name if name.endswith(".py") else f"{name}.py")).resolve()
            if path.parent != root or path.suffix != ".py":
                raise ValueError(
                    f"Custom tool module is outside the configured directory: {name}"
                )
            if not path.is_file():
                raise FileNotFoundError(f"Custom tool module not found: {name}")
            candidates.append(path)
        return candidates
    return sorted(path for path in root.glob("*.py") if not path.name.startswith("_"))


def _module_name(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    return f"shinkou_custom_{path.stem}_{digest}"


def _load_module(module_name: str, path: Path) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"unable to create import spec for {path.name}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    return module


def _register_module(
    registry: Any, module: ModuleType, report: CustomToolLoadReport
) -> None:
    before = {spec.name for spec in registry.specs()}
    hook = getattr(module, "register_tools", None)
    if callable(hook):
        hook(_CustomRegistryView(registry))

    report.tools.extend(
        name
        for name in (spec.name for spec in registry.specs())
        if name not in before and name not in report.tools
    )

    for name, handler in vars(module).items():
        spec = getattr(handler, CUSTOM_TOOL_SPEC, None)
        if (
            spec is None
            or not callable(handler)
            or getattr(handler, "__module__", None) != module.__name__
        ):
            continue
        if registry.has_tool(spec.name):
            continue
        registry.register(spec, handler, source="custom")
        report.tools.append(spec.name)


class _CustomRegistryView:
    """Keep legacy ``register_tools(registry)`` modules in the custom scope."""

    def __init__(self, registry: Any):
        self._registry = registry

    def register(self, spec: Any, handler: Any, **_: Any) -> None:
        self._registry.register(spec, handler, source="custom")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._registry, name)
