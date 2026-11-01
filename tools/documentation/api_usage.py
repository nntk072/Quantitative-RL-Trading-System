#!/usr/bin/env python3
"""Generate semantic usage references for the public Python API."""

from __future__ import annotations

import argparse
import ast
import json
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.documentation.public_api_inventory import (
    PUBLIC_CLASSIFICATIONS,
    PUBLIC_KINDS,
    ROOT,
    _production_roots,
    build_inventory,
)

OUTPUT = ROOT / "docs/api/usage"
MAX_EXAMPLES = 2
MAX_CONTEXT_LINES = 14
GOOGLE_SECTION = re.compile(
    r"(?m)^(Args|Returns|Yields|Raises|Examples|Notes?|Warnings|Attributes|Methods|See Also|References):\s*$"
)


@dataclass(frozen=True)
class CallSite:
    """One source-backed invocation with its reader-facing caller context."""

    path: Path
    line: int
    caller: str
    excerpt: str
    is_test: bool


def _module_name(path: Path, root: Path) -> str:
    """Return a dotted import name for a repository Python file."""
    return ".".join(path.relative_to(root).with_suffix("").parts).removesuffix(".__init__")


def _unparse_call_name(node: ast.expr) -> str:
    """Return a source-level dotted call name when the callee is a name or attribute."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _unparse_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _imports(tree: ast.Module, module: str) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Map local imported names and module aliases to their declared targets."""
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_PUBLIC_EXPORTS"
            for target in node.targets
        ):
            try:
                lazy_exports = ast.literal_eval(node.value)
            except (TypeError, ValueError):
                lazy_exports = {}
            if isinstance(lazy_exports, dict):
                for export, target in lazy_exports.items():
                    if (
                        isinstance(export, str)
                        and isinstance(target, tuple)
                        and len(target) == 2
                        and all(isinstance(part, str) for part in target)
                    ):
                        names[export] = (target[0], target[1])
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = module.split(".")
                package = parts if module.endswith(".__init__") else parts[:-1]
                parent = package[: max(0, len(package) - node.level + 1)]
                source = ".".join((*parent, *(node.module or "").split(".")))
            else:
                source = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    names[alias.asname or alias.name] = (source, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                modules[local] = alias.name
    return names, modules


def _parent_index(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Map child nodes to parents for caller and class scope recovery."""
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _clean_excerpt(source: str) -> str:
    """Dedent an example and remove trailing whitespace from source lines."""
    return "\n".join(line.rstrip() for line in textwrap.dedent(source).splitlines()).strip("\n")


def _enclosing_context(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ast.AST]:
    """Find the closest named function or class containing a call."""
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return current.name, current
    return "module scope", node


def _source_excerpt(path: Path, call: ast.Call | ast.Attribute, context: ast.AST) -> str:
    """Return bounded real source lines around a call, preserving its caller label."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = getattr(context, "lineno", call.lineno)
    end = getattr(context, "end_lineno", call.end_lineno or call.lineno)
    if isinstance(context, (ast.FunctionDef, ast.AsyncFunctionDef)):
        body = context.body
        has_docstring = bool(
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        )
        if has_docstring:
            start = body[1].lineno if len(body) > 1 else call.lineno
    if end - start + 1 <= MAX_CONTEXT_LINES:
        excerpt = "\n".join(lines[start - 1 : end])
        if isinstance(context, (ast.FunctionDef, ast.AsyncFunctionDef)):
            header_end = body[0].lineno - 1 if has_docstring else start - 1
            header = "\n".join(lines[context.lineno - 1 : header_end])
            if header:
                excerpt = f"{header}\n{excerpt}"
        return _clean_excerpt(excerpt)
    before = max(start, call.lineno - 5)
    after = min(end, call.end_lineno + 5 if call.end_lineno else call.lineno + 5)
    excerpt_lines = lines[before - 1 : after]
    if before > start:
        excerpt_lines.insert(0, "# … caller setup omitted …")
    if after < end:
        excerpt_lines.append("# … caller assertions omitted …")
    return _clean_excerpt("\n".join(excerpt_lines))


def _class_aliases(
    tree: ast.Module,
    imported: dict[str, tuple[str, str]],
    current_module: str,
    targets: set[tuple[str, str]],
    return_types: dict[tuple[str, str], tuple[str, str]],
) -> dict[str, tuple[str, str]]:
    """Resolve local aliases for imported or locally defined target classes."""
    aliases = {local: target for local, target in imported.items() if target in targets}
    aliases.update(
        {name: (current_module, name) for module, name in targets if module == current_module}
    )
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            call_name = _unparse_call_name(value.func)
            local_target = imported.get(call_name)
            if local_target is None and "." not in call_name:
                local_target = (current_module, call_name)
            returned_class = return_types.get(local_target) if local_target else None
            if returned_class is None and "." in call_name:
                class_alias, _, method_name = call_name.partition(".")
                class_owner = aliases.get(class_alias)
                if class_owner is None and (current_module, class_alias) in targets:
                    class_owner = (current_module, class_alias)
                if class_owner is not None:
                    returned_class = return_types.get(
                        (class_owner[0], f"{class_owner[1]}.{method_name}")
                    )
            if returned_class in targets:
                destinations = node.targets if isinstance(node, ast.Assign) else [node.target]
                for destination in destinations:
                    if isinstance(destination, ast.Name):
                        aliases[destination.id] = returned_class
            if local_target in targets:
                destinations = node.targets if isinstance(node, ast.Assign) else [node.target]
                for destination in destinations:
                    if isinstance(destination, ast.Name):
                        aliases[destination.id] = local_target
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotation = node.annotation
            if isinstance(annotation, ast.Name) and annotation.id in aliases:
                aliases[node.target.id] = aliases[annotation.id]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                if isinstance(argument.annotation, ast.Name) and argument.annotation.id in aliases:
                    aliases[argument.arg] = aliases[argument.annotation.id]
    return aliases


def _candidate_entries(
    call: ast.Call | ast.Attribute,
    *,
    module: str,
    imports: dict[str, tuple[str, str]],
    module_aliases: dict[str, str],
    class_aliases: dict[str, tuple[str, str]],
    parents: dict[ast.AST, ast.AST],
) -> list[dict[str, Any]]:
    """Resolve a call to public API entries using exact module/class ownership."""
    candidates: list[dict[str, Any]] = []
    function = call.func if isinstance(call, ast.Call) else call
    if isinstance(function, ast.Attribute):
        method_name = function.attr
        receiver = function.value
        owner: tuple[str, str] | None = None
        if isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}:
            current_node: ast.AST = call
            while current_node in parents:
                current_node = parents[current_node]
                if isinstance(current_node, ast.ClassDef):
                    owner = (module, current_node.name)
                    break
        elif isinstance(receiver, ast.Name):
            owner = class_aliases.get(receiver.id)
        elif isinstance(receiver, ast.Call):
            called = _unparse_call_name(receiver.func)
            class_target = class_aliases.get(called)
            if class_target is None and "." not in called:
                function_target = imports.get(called) or (module, called)
                class_target = RETURN_TYPES.get(function_target)
            if class_target is None and "." in called:
                head, _, tail = called.partition(".")
                target_module = module_aliases.get(head)
                class_target = RETURN_TYPES.get((target_module, tail)) if target_module else None
            if class_target is not None:
                owner = class_target
            elif module == called.rpartition(".")[0] and called:
                owner = (module, called.rpartition(".")[2])
        if owner is not None:
            candidates.extend(METHODS_BY_OWNER.get((*owner, method_name), ()))
            if not candidates:
                candidates.extend(_inherited_methods(owner, method_name))
        qualified = _unparse_call_name(function)
        head, _, tail = qualified.partition(".")
        if isinstance(call, ast.Call) and head in module_aliases:
            target_module = module_aliases[head]
            candidates.extend(ENTRIES_BY_SYMBOL.get((target_module, tail), ()))
        return candidates

    if isinstance(function, ast.Name):
        local_name = function.id
        target = imports.get(local_name)
        if target is not None:
            candidates.extend(ENTRIES_BY_SYMBOL.get(target, ()))
        candidates.extend(ENTRIES_BY_SYMBOL.get((module, local_name), ()))
    return candidates


ENTRIES_BY_SYMBOL: dict[tuple[str, str], list[dict[str, Any]]] = {}
METHODS_BY_OWNER: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
RETURN_TYPES: dict[tuple[str, str], tuple[str, str]] = {}
BASE_CLASSES: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}


def _index_entries(entries: list[dict[str, Any]]) -> None:
    """Index public exports and methods for constant-time call resolution."""
    ENTRIES_BY_SYMBOL.clear()
    METHODS_BY_OWNER.clear()
    for entry in entries:
        source_module = entry.get("source_module")
        if not source_module:
            continue
        public_name = str(entry["name"]).split(" (alias for", maxsplit=1)[0]
        alias = re.search(r"\(alias for ([^)]+)\)", str(entry["name"]))
        source_name = alias.group(1) if alias else public_name
        if entry["kind"] == "method":
            class_name, method_name = public_name.rsplit(".", maxsplit=1)
            METHODS_BY_OWNER.setdefault((source_module, class_name, method_name), []).append(entry)
        else:
            ENTRIES_BY_SYMBOL.setdefault((source_module, source_name), []).append(entry)


def _function_return_types(
    root: Path, entries: list[dict[str, Any]]
) -> dict[tuple[str, str], tuple[str, str]]:
    """Infer direct class return types from annotations and return constructors."""
    targets = {
        (entry["source_module"], str(entry["name"]).split(" (alias for", maxsplit=1)[0])
        for entry in entries
        if entry["kind"] == "class" and entry.get("source_module")
    }
    package_roots = _production_roots(root)
    files = [path for package in package_roots for path in sorted((root / package).rglob("*.py"))]
    results: dict[tuple[str, str], tuple[str, str]] = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        module = _module_name(path, root)
        imports, module_aliases = _imports(tree, module)
        local_classes = {
            (module, node.name) for node in tree.body if isinstance(node, ast.ClassDef)
        }
        aliases = _class_aliases(tree, imports, module, targets | local_classes, {})
        parents = _parent_index(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            owner_class = ""
            current: ast.AST = node
            while current in parents:
                current = parents[current]
                if isinstance(current, ast.ClassDef):
                    owner_class = current.name
                    break
            function_name = f"{owner_class}.{node.name}" if owner_class else node.name
            owner: tuple[str, str] | None = None
            annotation = node.returns
            if isinstance(annotation, ast.Name):
                owner = aliases.get(annotation.id)
                if owner is None and (module, annotation.id) in targets | local_classes:
                    owner = (module, annotation.id)
            elif isinstance(annotation, ast.Attribute):
                qualified = _unparse_call_name(annotation)
                head, _, tail = qualified.partition(".")
                if head in module_aliases:
                    owner = (module_aliases[head], tail)
            if owner is None:
                for current in ast.walk(node):
                    if not isinstance(current, ast.Return) or not isinstance(
                        current.value, ast.Call
                    ):
                        continue
                    name = _unparse_call_name(current.value.func)
                    candidate = imports.get(name)
                    if candidate is None and "." not in name:
                        candidate = (module, name)
                    if candidate in targets | local_classes:
                        owner = candidate
                        break
            if owner in targets:
                results[(module, function_name)] = owner
    return results


def _class_bases(
    root: Path, entries: list[dict[str, Any]]
) -> dict[tuple[str, str], tuple[tuple[str, str], ...]]:
    """Resolve statically named base classes for public API classes."""
    targets = {
        (entry["source_module"], str(entry["name"]).split(" (alias for", maxsplit=1)[0])
        for entry in entries
        if entry["kind"] == "class" and entry.get("source_module")
    }
    result: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
    for package in _production_roots(root):
        for path in sorted((root / package).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            module = _module_name(path, root)
            imports, _module_aliases = _imports(tree, module)
            for node in (item for item in tree.body if isinstance(item, ast.ClassDef)):
                bases: list[tuple[str, str]] = []
                for base in node.bases:
                    name = _unparse_call_name(base)
                    target = imports.get(name)
                    if target is None and "." not in name:
                        target = (module, name)
                    elif target is None:
                        head, _, tail = name.partition(".")
                        target = (imports[head][0], tail) if head in imports else None
                    if target in targets:
                        bases.append(target)
                if bases:
                    result[(module, node.name)] = tuple(bases)
    return result


def _inherited_methods(owner: tuple[str, str], method: str) -> list[dict[str, Any]]:
    """Return public methods implemented by a statically known base class."""
    candidates: list[dict[str, Any]] = []
    pending = list(BASE_CLASSES.get(owner, ()))
    visited = {owner}
    while pending:
        base = pending.pop(0)
        if base in visited:
            continue
        visited.add(base)
        candidates.extend(METHODS_BY_OWNER.get((*base, method), ()))
        pending.extend(BASE_CLASSES.get(base, ()))
    return candidates


def collect_call_sites(root: Path = ROOT) -> dict[str, list[CallSite]]:
    """Collect real production/test invocations for stable public callables."""
    inventory = build_inventory(root)
    entries = [
        entry
        for entry in inventory["entries"]
        if entry["classification"] in PUBLIC_CLASSIFICATIONS
        and entry["kind"] in PUBLIC_KINDS
        and entry.get("source_module")
    ]
    _index_entries(entries)
    return_types = _function_return_types(root, entries)
    RETURN_TYPES.clear()
    RETURN_TYPES.update(return_types)
    BASE_CLASSES.clear()
    BASE_CLASSES.update(_class_bases(root, entries))
    package_roots = (*_production_roots(root), "tests")
    files = [path for package in package_roots for path in sorted((root / package).rglob("*.py"))]
    files.extend(
        path
        for path in sorted((root / "docs").rglob("*.ipynb"))
        if "_build" not in path.parts and "generated" not in path.parts
    )
    results: dict[str, list[CallSite]] = defaultdict(list)
    for path in files:
        if "__pycache__" in path.parts:
            continue
        notebook_cells: list[tuple[int, int, int]] = []
        try:
            if path.suffix == ".ipynb":
                notebook = json.loads(path.read_text(encoding="utf-8"))
                source_parts: list[str] = []
                current_line = 1
                for cell_number, cell in enumerate(notebook.get("cells", []), start=1):
                    if cell.get("cell_type") != "code":
                        continue
                    cell_source = cell.get("source", "")
                    cell_text = (
                        "".join(cell_source) if isinstance(cell_source, list) else str(cell_source)
                    )
                    if not cell_text.strip():
                        continue
                    start_line = current_line
                    source_parts.append(cell_text)
                    current_line += len(cell_text.splitlines()) + 2
                    notebook_cells.append((start_line, current_line - 2, cell_number))
                    source_parts.append("\n\n")
                source = "".join(source_parts)
            else:
                source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        module = _module_name(path, root)
        imports, module_aliases = _imports(tree, module)
        relevant_classes = {
            (entry["source_module"], entry["name"].split(".", maxsplit=1)[0])
            for entry in entries
            if entry["kind"] == "method"
        }
        class_aliases = _class_aliases(tree, imports, module, relevant_classes, return_types)
        parents = _parent_index(tree)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        for call in calls:
            for entry in _candidate_entries(
                call,
                module=module,
                imports=imports,
                module_aliases=module_aliases,
                class_aliases=class_aliases,
                parents=parents,
            ):
                caller, context = _enclosing_context(call, parents)
                excerpt = _source_excerpt(path, call, context)
                line = call.lineno
                if notebook_cells:
                    cell = next(
                        (
                            (start, end, number)
                            for start, end, number in notebook_cells
                            if start <= call.lineno <= end
                        ),
                        None,
                    )
                    if cell:
                        start, end, number = cell
                        caller = f"{path.stem} · code cell {number}"
                        excerpt = _clean_excerpt("\n".join(source.splitlines()[start - 1 : end]))
                        line = 1
                key = f"{entry['source_module']}::{entry['name']}::{entry['kind']}"
                results[key].append(
                    CallSite(
                        path=path,
                        line=line,
                        caller=caller,
                        excerpt=excerpt,
                        is_test="tests" in path.parts,
                    )
                )
        for attribute in (node for node in ast.walk(tree) if isinstance(node, ast.Attribute)):
            parent = parents.get(attribute)
            if isinstance(parent, ast.Call) and parent.func is attribute:
                continue
            for entry in _candidate_entries(
                attribute,
                module=module,
                imports=imports,
                module_aliases=module_aliases,
                class_aliases=class_aliases,
                parents=parents,
            ):
                if entry["kind"] != "method":
                    continue
                caller, context = _enclosing_context(attribute, parents)
                excerpt = _source_excerpt(path, attribute, context)
                line = attribute.lineno
                if notebook_cells:
                    cell = next(
                        (
                            (start, end, number)
                            for start, end, number in notebook_cells
                            if start <= attribute.lineno <= end
                        ),
                        None,
                    )
                    if cell:
                        start, end, number = cell
                        caller = f"{path.stem} · code cell {number}"
                        excerpt = _clean_excerpt("\n".join(source.splitlines()[start - 1 : end]))
                        line = 1
                key = f"{entry['source_module']}::{entry['name']}::{entry['kind']}"
                results[key].append(
                    CallSite(
                        path=path,
                        line=line,
                        caller=caller,
                        excerpt=excerpt,
                        is_test="tests" in path.parts,
                    )
                )
    for values in results.values():
        values.sort(key=lambda site: (not site.is_test, str(site.path), site.line))
    return results


def _entry_key(entry: dict[str, Any]) -> str:
    """Return the stable call-site key for a public inventory entry."""
    return f"{entry.get('source_module')}::{entry['name']}::{entry['kind']}"


def _summary(entry: dict[str, Any], source: Path) -> str:
    """Extract the first useful Google-style summary line from source."""
    if not entry.get("source_line"):
        return "This export does not resolve to a repository definition."
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != entry["source_line"]:
            continue
        doc = (
            ast.get_docstring(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            else None
        )
        if doc:
            return doc.strip().splitlines()[0].strip()
    return "No source summary is available."


def _contract_sections(entry: dict[str, Any], source: Path) -> dict[str, str]:
    """Extract input, output, and failure contracts from the Google docstring."""
    if not entry.get("source_line"):
        return {}
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    docstring: str | None = None
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) == entry["source_line"] and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            docstring = ast.get_docstring(node)
            break
    if not docstring:
        return {}
    sections: dict[str, str] = {}
    matches = list(GOOGLE_SECTION.finditer(docstring))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(docstring)
        sections[match.group(1)] = textwrap.dedent(docstring[match.end() : end]).strip()
    return sections


def _render_contract(page: list[str], entry: dict[str, Any], source: Path) -> None:
    """Render source-defined input/output behavior in reader-facing sections."""
    sections = _contract_sections(entry, source)
    if not sections:
        return
    page.extend(["**Inputs and outputs:**", ""])
    for label in ("Args", "Returns", "Yields", "Raises", "Examples"):
        content = sections.get(label)
        if content:
            page.extend([f"- **{label}:**", "", "  ```text"])
            page.extend([f"  {line}" if line else "" for line in content.splitlines()])
            page.extend(["  ```", ""])


def _class_context(entry: dict[str, Any], root: Path) -> str | None:
    """Describe the owning class lifecycle for a callable without a resolved call site."""
    source = root / entry["source_path"]
    if not entry.get("source_line"):
        return None
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    parents = _parent_index(tree)
    definition = next(
        (
            node
            for node in ast.walk(tree)
            if getattr(node, "lineno", None) == entry["source_line"]
            and isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            )
        ),
        None,
    )
    if definition is None:
        return None
    current: ast.AST = definition
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.ClassDef):
            summary = (ast.get_docstring(current) or "").splitlines()
            purpose = summary[0].strip() if summary else "No class summary is available."
            siblings = [
                node.name
                for node in current.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            ]
            related = ", ".join(
                f"{{py:obj}}`{entry['source_module']}.{current.name}.{name}`"
                for name in siblings[:8]
            )
            return (
                f"This callable participates in `{current.name}`: {purpose} "
                f"Related public lifecycle methods: {related or 'none declared'}"
            )
    if isinstance(definition, ast.ClassDef):
        summary = (ast.get_docstring(definition) or "").splitlines()
        return summary[0].strip() if summary else None
    return None


def _invocation_shape(entry: dict[str, Any], root: Path) -> str | None:
    """Render a syntax-accurate call shape when no real example is available."""
    source = root / entry["source_path"]
    if not entry.get("source_line"):
        return None
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    definition = next(
        (
            node
            for node in ast.walk(tree)
            if getattr(node, "lineno", None) == entry["source_line"]
            and isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            )
        ),
        None,
    )
    if isinstance(definition, ast.ClassDef):
        initializer = next(
            (
                node
                for node in definition.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "__init__"
            ),
            None,
        )
        arguments = _argument_shape(initializer.args) if initializer else "..."
        return f"instance = {definition.name}({arguments})"
    if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    args = _argument_shape(definition.args)
    owner = entry["name"].rsplit(".", maxsplit=1)[0] if entry["kind"] == "method" else None
    is_static = any(
        isinstance(decorator, ast.Name) and decorator.id == "staticmethod"
        for decorator in definition.decorator_list
    )
    is_classmethod = any(
        isinstance(decorator, ast.Name) and decorator.id == "classmethod"
        for decorator in definition.decorator_list
    )
    is_property = any(
        isinstance(decorator, ast.Name) and decorator.id == "property"
        for decorator in definition.decorator_list
    )
    if owner and (is_static or is_classmethod):
        call = f"{owner}.{definition.name}({args})"
    elif owner:
        if is_property:
            return f"instance = {owner.rsplit('.', maxsplit=1)[-1]}(...)\nvalue = instance.{definition.name}"
        call = f"instance.{definition.name}({args})"
    else:
        call = f"{definition.name}({args})"
    prefix = "await " if isinstance(definition, ast.AsyncFunctionDef) else ""
    invocation = f"result = {prefix}{call}"
    if owner and not (is_static or is_classmethod):
        invocation = f"instance = {owner.rsplit('.', maxsplit=1)[-1]}(...)\n{invocation}"
    return invocation


def _argument_shape(arguments: ast.arguments | None) -> str:
    """Return a placeholder argument list matching a Python signature's syntax."""
    if arguments is None:
        return "..."
    values: list[str] = []
    positional_only = list(arguments.posonlyargs)
    regular = list(arguments.args)
    if regular and regular[0].arg in {"self", "cls"}:
        regular = regular[1:]
    for argument in positional_only:
        if argument.arg not in {"self", "cls"}:
            values.append("...")
    values.extend(f"{argument.arg}=..." for argument in regular)
    values.extend(f"*{arguments.vararg.arg}" for _ in [0] if arguments.vararg is not None)
    values.extend(f"{argument.arg}=..." for argument in arguments.kwonlyargs)
    values.extend(f"**{arguments.kwarg.arg}" for _ in [0] if arguments.kwarg is not None)
    return ", ".join(values) if values else ""


def render_usage_pages(root: Path = ROOT) -> dict[Path, str]:
    """Render package usage guides with source-linked invocation examples."""
    inventory = build_inventory(root)
    sites = collect_call_sites(root)
    entries = [
        entry
        for entry in inventory["entries"]
        if entry["classification"] in PUBLIC_CLASSIFICATIONS and entry["kind"] in PUBLIC_KINDS
    ]
    by_package: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_module: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_package[entry["package"]].append(entry)
        by_module[(entry["package"], str(entry["source_module"]))].append(entry)
    outputs: dict[Path, str] = {}
    title = {
        "artifacts": "Artifacts",
        "compute": "Compute",
        "configuration": "Configuration",
        "decisioning": "Decisioning",
        "evaluation": "Evaluation",
        "experiments": "Experiments",
        "features": "Features",
        "integrations": "Integrations",
        "learning": "Learning",
        "live": "Live runtime",
        "market_data": "Market data",
        "models": "Models",
        "orchestra": "Orchestra",
        "simulation": "Simulation",
        "tools": "Tooling",
        "trading": "Trading",
        "training": "Training",
    }
    domain_by_package = {
        "artifacts": "workflows",
        "compute": "engineering",
        "configuration": "configuration",
        "decisioning": "trading",
        "evaluation": "workflows",
        "experiments": "workflows",
        "features": "data",
        "integrations": "runtime",
        "learning": "models",
        "live": "runtime",
        "market_data": "data",
        "models": "models",
        "orchestra": "engineering",
        "simulation": "trading",
        "tools": "engineering",
        "trading": "trading",
        "training": "workflows",
    }
    site_coverage = sum(bool(sites.get(_entry_key(entry))) for entry in entries)
    index = [
        "# Function usage and context",
        "",
        "This guide connects every exported callable to its owner, workflow context, and the strongest source-backed usage evidence available. Examples are real call-site excerpts from implementation code, tutorials, or tests; fixture-dependent excerpts link to their source test. An explicit no-call-site label means repository analysis found no direct invocation, so the page gives the owning lifecycle and complete contract without inventing a recipe.",
        "",
        f"Current source call-site coverage: {site_coverage} of {len(entries)} callable records.",
        "",
        "```{toctree}",
        ":maxdepth: 1",
        "",
    ]
    for package in sorted(by_package):
        package_modules = sorted(module for owner, module in by_module if owner == package)
        index.append(f"{package}/index")
        package_index = [
            f"# {title.get(package, package)} function usage",
            "",
            f"This guide contains {len(by_package[package])} public callable records across {len(package_modules)} source modules. Choose a module for function-level purpose, contract, verified call paths, and lifecycle context.",
            "",
            "```{toctree}",
            ":maxdepth: 1",
            ":caption: Source modules",
            "",
        ]
        for module in package_modules:
            relative_module = module.removeprefix(f"{package}.")
            filename = f"{module.replace('.', '__')}.md"
            package_index.append(filename.removesuffix(".md"))
            page = [
                f"# {title.get(package, package)} · `{relative_module}`",
                "",
                f"This page contains {len(by_module[(package, module)])} public callable records owned by `{module}`. Status reflects the exported contract, not a promise that all internal behavior is stable.",
                "",
            ]
            for entry in sorted(
                by_module[(package, module)],
                key=lambda row: (row["exported_from"], row["name"]),
            ):
                name = str(entry["name"])
                display_name = name.split(" (alias for", maxsplit=1)[0]
                alias = re.search(r"\(alias for ([^)]+)\)", name)
                source_name = alias.group(1) if alias else display_name
                symbol = f"{entry['source_module']}.{source_name}"
                source_anchor = f"#L{entry['source_line']}" if entry.get("source_line") else ""
                page.extend(
                    [
                        f"## `{display_name}`",
                        "",
                        f"**Kind:** {entry['kind']} · **Status:** {entry['classification']} · **Owner:** `{entry['source_module']}`",
                        "",
                        f"**Purpose:** {_summary(entry, root / entry['source_path'])}",
                        "",
                        f"**Exact API:** {{py:obj}}`{symbol}` · **Source:** [{entry['source_path']}:{entry['source_line'] or 'export'}](../../../../{entry['source_path']}{source_anchor})",
                        "",
                    ]
                )
                _render_contract(page, entry, root / entry["source_path"])
                matches = sites.get(_entry_key(entry), [])
                if matches:
                    page.extend(["**Observed usage:**", ""])
                    unique: set[tuple[str, str]] = set()
                    included = 0
                    for site in matches:
                        identity = (site.path.as_posix(), site.caller)
                        if identity in unique:
                            continue
                        unique.add(identity)
                        kind = (
                            "test fixture"
                            if site.is_test
                            else "tutorial example"
                            if "docs" in site.path.parts
                            else "production caller"
                        )
                        anchor = f"#L{site.line}" if site.path.suffix != ".ipynb" else ""
                        page.extend(
                            [
                                f"{included + 1}. [{kind}: `{site.caller}`](../../../../{site.path.relative_to(root).as_posix()}{anchor})",
                                "",
                                "Source excerpt (not standalone); follow the linked caller for imports and setup.",
                                "",
                                "```python",
                                site.excerpt,
                                "```",
                                "",
                            ]
                        )
                        included += 1
                        if included >= MAX_EXAMPLES:
                            break
                    if all(site.is_test for site in matches[:MAX_EXAMPLES]):
                        page.append(
                            "These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them."
                        )
                        page.append("")
                else:
                    source_examples = _contract_sections(entry, root / entry["source_path"]).get(
                        "Examples"
                    )
                    if source_examples:
                        page.extend(
                            [
                                "**Documented usage from the source contract:**",
                                "",
                                "```text",
                                source_examples,
                                "```",
                                "",
                            ]
                        )
                    else:
                        class_context = _class_context(entry, root)
                        invocation = _invocation_shape(entry, root)
                        context = (
                            f"**Lifecycle context:** {class_context}"
                            if class_context
                            else "**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide."
                        )
                        page.extend(
                            [
                                "**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.",
                                "",
                                "**Invocation shape (placeholders):**",
                                "",
                                "Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.",
                                "",
                                "```python",
                                invocation
                                or "# See the exact signature in the generated API reference.",
                                "```",
                                "",
                                context,
                                "",
                                "The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.",
                                "",
                            ]
                        )
                page.extend(
                    [
                        "**Workflow context:**",
                        "",
                        f"- Semantic domain guide: {{doc}}`../../domains/{domain_by_package[package]}`",
                        f"- Generated package reference: {{doc}}`../../generated/{package}/index`",
                        "",
                    ]
                )
            outputs[OUTPUT / package / filename] = "\n".join(page).rstrip() + "\n"
        package_index.extend(["```", ""])
        outputs[OUTPUT / package / "index.md"] = "\n".join(package_index)
    index.extend(
        [
            "```",
            "",
            "## Coverage",
            "",
            f"This generated index contains {len(entries)} callable records. Rebuild and verify it with `python -m tools.documentation.api_usage --write` and `--check`.",
            "",
        ]
    )
    outputs[OUTPUT / "index.md"] = "\n".join(index)
    return outputs


def main(argv: list[str] | None = None) -> int:
    """Generate or check the function-level usage guides."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = render_usage_pages()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for package in {
            entry["package"]
            for entry in build_inventory()["entries"]
            if entry["classification"] in PUBLIC_CLASSIFICATIONS and entry["kind"] in PUBLIC_KINDS
        }:
            legacy_page = OUTPUT / f"{package}.md"
            if legacy_page.is_file():
                legacy_page.unlink()
        expected_paths = set(outputs)
        for stale_page in OUTPUT.rglob("*.md"):
            if stale_page not in expected_paths:
                stale_page.unlink()
        print(
            f"Wrote {sum(len(content.splitlines()) for content in outputs.values()):,} lines across {len(outputs)} API usage pages."
        )
        return 0
    stale = [
        str(path.relative_to(ROOT))
        for path, content in outputs.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    if stale:
        print("Function API usage pages are stale:")
        for stale_path in stale:
            print(f"- {stale_path}")
        return 1
    print(f"Function API usage guides are current ({len(outputs)} navigable pages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
