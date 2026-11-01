"""Generate and check the source-defined Python API inventory.

Package ``__all__`` declarations define exported names. Package initializers
identify supported boundaries; other module exports are internal contracts.
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
NUMPY_SECTION = re.compile(
    r"^\s*(?:Parameters(?:\s*\([^\n]*\))?|Returns|Yields|Raises|Attributes|Methods|"
    r"Notes|Warnings|See Also|References|Examples|Other Parameters)\s*:?\s*\n\s*-{3,}\s*$",
    re.MULTILINE,
)
PUBLIC_KINDS = {"class", "function", "method"}
PUBLIC_CLASSIFICATIONS = {"stable", "experimental", "compatibility-only"}
COMPATIBILITY_MODULES = {"models.encoders.core"}


@dataclass(frozen=True)
class ModuleInfo:
    """Parsed source declarations needed for static export resolution."""

    module: str
    path: Path
    tree: ast.Module
    exports: tuple[str, ...]
    definitions: dict[str, ast.AST]
    imports: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class ApiEntry:
    """One exported name or public method and its source documentation state."""

    package: str
    exported_from: str
    name: str
    source_module: str | None
    source_path: str
    source_line: int | None
    kind: str
    classification: str
    documented: bool
    numpy_style: bool


def _production_roots(root: Path) -> tuple[str, ...]:
    """Read package roots from the wheel configuration."""
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    roots = document["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    return tuple(str(item) for item in roots)


def _module_name(path: Path, root: Path) -> str:
    """Return a package-qualified module name for a Python source path."""
    module = ".".join(path.relative_to(root).with_suffix("").parts)
    return module.removesuffix(".__init__")


def _all_names(tree: ast.Module) -> tuple[str, ...]:
    """Read literal string names from ``__all__`` assignments."""
    literal_values: dict[str, ast.expr] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    literal_values[target.id] = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.value is not None:
                literal_values[statement.target.id] = statement.value
    names: list[str] = []
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "__all__":
                value = node.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "__all__":
                value = node.value
        if value is None:
            continue
        candidate = _literal_export_value(value, literal_values)
        names.extend(item for item in candidate if isinstance(item, str))
    return tuple(dict.fromkeys(names))


def _literal_export_value(value: ast.expr, assignments: dict[str, ast.expr]) -> list[str]:
    """Resolve a literal export list or a list made from a literal map's keys."""
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        return _literal_export_value(value.left, assignments) + _literal_export_value(
            value.right, assignments
        )
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "list":
        if value.args and isinstance(value.args[0], ast.Name):
            assigned = assignments.get(value.args[0].id)
            if assigned is not None:
                try:
                    candidate = ast.literal_eval(assigned)
                except (TypeError, ValueError):
                    return []
                if isinstance(candidate, dict):
                    return [key for key in candidate if isinstance(key, str)]
    try:
        candidate = ast.literal_eval(value)
    except (TypeError, ValueError):
        return []
    if isinstance(candidate, (list, tuple, set)):
        return [item for item in candidate if isinstance(item, str)]
    return []


def _module_declarations(tree: ast.Module) -> dict[str, ast.AST]:
    """Index top-level definitions and named values by their local names."""
    declarations: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            declarations[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declarations[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            declarations[node.target.id] = node
    return declarations


def _relative_module(module: str, path: Path, node: ast.ImportFrom) -> str:
    """Resolve the destination module of an absolute or relative import."""
    if node.level == 0:
        return node.module or ""
    components = module.split(".")
    package = components if path.name == "__init__.py" else components[:-1]
    parent = package[: max(0, len(package) - node.level + 1)]
    suffix = node.module.split(".") if node.module else []
    return ".".join((*parent, *suffix))


def _module_imports(module: str, path: Path, tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Map imported local names to their statically resolvable source symbols."""
    imports: dict[str, tuple[str, str]] = {}
    lazy_exports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_PUBLIC_EXPORTS"
            for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (TypeError, ValueError):
                value = None
            if isinstance(value, dict):
                for export, destination in value.items():
                    if (
                        isinstance(export, str)
                        and isinstance(destination, tuple)
                        and len(destination) == 2
                        and all(isinstance(part, str) for part in destination)
                    ):
                        lazy_exports[export] = (destination[0], destination[1])
        if not isinstance(node, ast.ImportFrom):
            continue
        imported_module = _relative_module(module, path, node)
        for alias in node.names:
            if alias.name != "*":
                imports[alias.asname or alias.name] = (imported_module, alias.name)
    return {**lazy_exports, **imports}


def load_modules(root: Path = ROOT) -> dict[str, ModuleInfo]:
    """Parse production Python files and capture their explicit exports."""
    modules: dict[str, ModuleInfo] = {}
    for package in _production_roots(root):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            module = _module_name(path, root)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            modules[module] = ModuleInfo(
                module=module,
                path=path,
                tree=tree,
                exports=_all_names(tree),
                definitions=_module_declarations(tree),
                imports=_module_imports(module, path, tree),
            )
    return modules


def _resolve(
    modules: dict[str, ModuleInfo],
    module: str,
    name: str,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[str, str, ast.AST] | None:
    """Follow local re-exports until a source declaration is found."""
    key = (module, name)
    if module not in modules or key in seen:
        return None
    current = modules[module]
    if name in current.definitions:
        return module, name, current.definitions[name]
    if name in current.imports:
        return _resolve(modules, *current.imports[name], seen | {key})
    return None


def _kind(node: ast.AST) -> str:
    """Name a source declaration kind for the generated inventory."""
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "function"
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return "value"
    return "external"


def _docstring(node: ast.AST) -> str | None:
    """Return a Python docstring only for AST nodes that can own one."""
    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return ast.get_docstring(node)
    return None


def _classification(name: str, export_module: ModuleInfo, source_module: str | None) -> str:
    """Classify one export by its declared boundary and compatibility status."""
    if name.startswith("_"):
        return "private implementation"
    if (
        "legacy" in name.lower()
        or "deprecated" in name.lower()
        or source_module in COMPATIBILITY_MODULES
    ):
        return "compatibility-only"
    if any(
        part in {"experimental", "research", "analysis"} for part in export_module.module.split(".")
    ):
        return "experimental"
    if export_module.path.name == "__init__.py":
        return "stable"
    return "cross-package internal"


def _entry(
    root: Path,
    modules: dict[str, ModuleInfo],
    export_module: ModuleInfo,
    name: str,
    resolved: tuple[str, str, ast.AST] | None,
) -> ApiEntry:
    """Build a serializable inventory record for one exported name."""
    source_module, source_name, node = resolved if resolved else (None, name, None)
    source = modules[source_module].path if source_module is not None else export_module.path
    if source_module is not None and node is not None:
        source_path = str(source.relative_to(root))
        line = getattr(node, "lineno", None)
        docstring = _docstring(node) or ""
        documented = bool(docstring)
    else:
        source_path = str(export_module.path.relative_to(root))
        line = None
        documented = False
        docstring = ""
    return ApiEntry(
        package=export_module.module.split(".")[0],
        exported_from=export_module.module,
        name=name if source_name == name else f"{name} (alias for {source_name})",
        source_module=source_module,
        source_path=source_path,
        source_line=line,
        kind=_kind(node) if node is not None else "external",
        classification=_classification(name, export_module, source_module),
        documented=documented,
        numpy_style=bool(NUMPY_SECTION.search(docstring)),
    )


def build_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Return all explicit exports and the methods exposed by exported classes."""
    modules = load_modules(root)
    entries: dict[tuple[str, str, str], ApiEntry] = {}
    classes: dict[tuple[str, str], tuple[ModuleInfo, ast.ClassDef, str]] = {}
    exported_definitions: set[tuple[str, str]] = set()
    for export_module in modules.values():
        for name in export_module.exports:
            resolved = _resolve(modules, export_module.module, name)
            entry = _entry(root, modules, export_module, name, resolved)
            entries[(entry.exported_from, entry.name, entry.kind)] = entry
            if resolved is not None:
                exported_definitions.add((resolved[0], resolved[1]))
            if (
                resolved is not None
                and isinstance(resolved[2], ast.ClassDef)
                and entry.classification in PUBLIC_CLASSIFICATIONS
            ):
                source_module = modules[resolved[0]]
                classes[(resolved[0], resolved[1])] = (
                    source_module,
                    resolved[2],
                    entry.classification,
                )
    for module in modules.values():
        for name, node in module.definitions.items():
            if not name.startswith("_") or (module.module, name) in exported_definitions:
                continue
            entry = ApiEntry(
                package=module.module.split(".")[0],
                exported_from=module.module,
                name=name,
                source_module=module.module,
                source_path=str(module.path.relative_to(root)),
                source_line=getattr(node, "lineno", None),
                kind=_kind(node),
                classification="private implementation",
                documented=bool(_docstring(node)),
                numpy_style=bool(NUMPY_SECTION.search(_docstring(node) or "")),
            )
            entries[(module.module, name, entry.kind)] = entry
    for (class_module, class_name), (source, cls, classification) in classes.items():
        for member in cls.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if member.name.startswith("_"):
                continue
            docstring = _docstring(member) or ""
            entries[(class_module, f"{class_name}.{member.name}", "method")] = ApiEntry(
                package=class_module.split(".")[0],
                exported_from=class_module,
                name=f"{class_name}.{member.name}",
                source_module=class_module,
                source_path=str(source.path.relative_to(root)),
                source_line=member.lineno,
                kind="method",
                classification=classification,
                documented=bool(docstring),
                numpy_style=bool(NUMPY_SECTION.search(docstring)),
            )
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    cli_commands = []
    for name, target in sorted(pyproject.get("project", {}).get("scripts", {}).items()):
        module_name = str(target).split(":", maxsplit=1)[0]
        command_module = modules.get(module_name)
        cli_commands.append(
            {
                "name": name,
                "target": str(target),
                "source_path": (
                    str(command_module.path.relative_to(root))
                    if command_module
                    else "pyproject.toml"
                ),
                "classification": "stable",
            }
        )
    return {
        "schema_version": 1,
        "source": "literal package __all__ declarations",
        "cli_commands": cli_commands,
        "entries": [
            asdict(item)
            for item in sorted(entries.values(), key=lambda e: (e.package, e.exported_from, e.name))
        ],
    }


def _production_numpy_docstrings(root: Path) -> list[str]:
    """List production source files that still use NumPy-style sections."""
    offenders: list[str] = []
    for package in _production_roots(root):
        for path in (root / package).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            nodes: list[ast.AST] = list(ast.walk(tree))
            if any(
                (docstring := _docstring(node)) is not None and NUMPY_SECTION.search(docstring)
                for node in nodes
            ):
                offenders.append(path.relative_to(root).as_posix())
    return sorted(offenders)


def _missing_public_docstrings(inventory: dict[str, Any]) -> list[str]:
    """Find undocumented stable/experimental/compatibility exports and methods."""
    failures = []
    for entry in inventory["entries"]:
        if (
            entry["classification"] in PUBLIC_CLASSIFICATIONS
            and entry["kind"] in PUBLIC_KINDS
            and not entry["documented"]
        ):
            failures.append(f"{entry['source_path']}:{entry['source_line']}: {entry['name']}")
    return failures


_GOOGLE_SECTION = re.compile(
    r"(?m)^(Args|Returns|Yields|Raises|Examples|Notes?|Warnings|Attributes|Methods|"
    r"See Also|References|Other Parameters):\s*$"
)
_GOOGLE_ARGUMENT = re.compile(r"^\s{4}(\*{0,2}[A-Za-z_]\w*)(?:\s+\([^\n]*\))?:\s*(.*)$")
_NONE_ANNOTATIONS = {"None", "NoneType", "NoReturn", "Never", "typing.NoReturn", "typing.Never"}


def _function_arguments(
    node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_method: bool
) -> list[str]:
    """Return function parameters that belong in a Google Args section."""
    arguments = [*node.args.posonlyargs, *node.args.args]
    excluded = {"self", "cls"} if is_method else set()
    names = [arg.arg for arg in arguments if arg.arg not in excluded]
    if node.args.vararg:
        names.append(f"*{node.args.vararg.arg}")
    names.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg:
        names.append(f"**{node.args.kwarg.arg}")
    return names


def _has_owned_yield(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a function yields values directly or through yield from."""

    def visit(current: ast.AST) -> bool:
        if current is not node and isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            return False
        if isinstance(current, (ast.Yield, ast.YieldFrom)):
            return True
        return any(visit(child) for child in ast.iter_child_nodes(current))

    return visit(node)


def _non_none_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a return annotation describes any value beyond ``None``."""
    if node.returns is None:
        return False
    annotation = ast.unparse(node.returns).replace("typing.", "")
    if annotation in _NONE_ANNOTATIONS:
        return False
    if isinstance(node.returns, ast.Constant) and node.returns.value is None:
        return False
    return True


def _production_function_docstring_gaps(root: Path = ROOT) -> list[str]:
    """Find missing Google summaries, parameter entries, and result descriptions."""
    failures: list[str] = []
    for package in _production_roots(root):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            methods: set[int] = set()

            class ScopeVisitor(ast.NodeVisitor):
                """Identify direct class methods so only bound self/cls are implicit."""

                def __init__(self) -> None:
                    self.scopes: list[str] = []

                def visit_ClassDef(self, node: ast.ClassDef) -> None:
                    self.scopes.append("class")
                    self.generic_visit(node)
                    self.scopes.pop()

                def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                    self._visit_function(node)

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                    self._visit_function(node)

                def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                    if self.scopes and self.scopes[-1] == "class":
                        methods.add(id(node))
                    self.scopes.append("function")
                    self.generic_visit(node)
                    self.scopes.pop()

            ScopeVisitor().visit(tree)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if any(
                    isinstance(decorator, ast.Name)
                    and decorator.id == "overload"
                    or isinstance(decorator, ast.Attribute)
                    and decorator.attr == "overload"
                    for decorator in node.decorator_list
                ):
                    continue
                location = f"{path.relative_to(root).as_posix()}:{node.lineno}:{node.name}"
                docstring = ast.get_docstring(node)
                if not docstring or not docstring.splitlines()[0].strip():
                    failures.append(f"{location}: missing summary/docstring")
                    continue

                sections: dict[str, str] = {}
                matches = list(_GOOGLE_SECTION.finditer(docstring))
                for index, match in enumerate(matches):
                    end = matches[index + 1].start() if index + 1 < len(matches) else len(docstring)
                    sections[match.group(1)] = docstring[match.end() : end]

                expected = _function_arguments(node, is_method=id(node) in methods)
                if expected:
                    documented: dict[str, str] = {}
                    for line in sections.get("Args", "").splitlines():
                        entry = _GOOGLE_ARGUMENT.match(line)
                        if entry:
                            documented[entry.group(1)] = entry.group(2).strip()
                    for argument in expected:
                        description = documented.get(argument)
                        if not description:
                            failures.append(f"{location}: missing Args entry for {argument}")

                if _non_none_return(node):
                    section = "Yields" if _has_owned_yield(node) else "Returns"
                    if not sections.get(section, "").strip():
                        failures.append(f"{location}: missing {section} description")
    return failures
