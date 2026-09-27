"""M0.5 — static verifier for a generated Next.js project (parse-only, ROADMAP D5).

Enforces the preview contract (docs/preview-contract.md) without building or running anything:
tree-sitter parse, import resolution, dependency allowlist, file conventions, server-only features
and the Server/Client Component boundary. M2.6 promotes the rules that earn their place.

    uv run python -m evals.spikes.m0_5.verifier PATH      # verify one project directory
"""

import json
import posixpath
import re
import sys
from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Node, Parser, Tree

_TSX = Parser(Language(ts_typescript.language_tsx()))
_TS = Parser(Language(ts_typescript.language_typescript()))
PARSERS = {".tsx": _TSX, ".jsx": _TSX, ".js": _TSX, ".mjs": _TSX, ".ts": _TS}

RESOLVE_EXTS = (".tsx", ".ts", ".jsx", ".js", ".mjs", ".json", ".css")
BINARY_EXTS = frozenset(
    ".png .jpg .jpeg .gif .webp .avif .ico .bmp .woff .woff2 .ttf .otf .eot .mp4 .webm .mov "
    ".mp3 .wav .ogg .pdf .zip .glb .hdr .exr .ktx2".split()
)
ASSET_EXTS = BINARY_EXTS | {".svg", ".gltf"}

# Preview contract, "Vetted dependencies" (2026-09-26): package -> (pinned version, status)
VETTED: dict[str, tuple[str, str]] = {
    "react": ("19.2.0", "allowed"),
    "react-dom": ("19.2.0", "allowed"),
    "motion": ("13.4.4", "allowed"),
    "lenis": ("1.3.26", "allowed"),
    "three": ("0.186.1", "allowed"),
    "@react-three/fiber": ("9.8.1", "allowed"),
    "@react-three/drei": ("10.7.9", "allowed"),
    "lucide-react": ("1.48.0", "allowed"),
    "clsx": ("2.1.1", "allowed"),
    "tailwind-merge": ("3.7.0", "allowed"),
    "gsap": ("3.15.0", "on_hold"),
    "@gsap/react": ("2.1.2", "on_hold"),
}
# `next` is shimmed by the preview; only these entry points exist
NEXT_SHIMMED = frozenset(
    {"next", "next/link", "next/image", "next/font/google", "next/navigation", "next/dynamic"}
)
FORBIDDEN_MODULES = {
    "next/headers": "server-only API",
    "next/server": "server-only API",
    "next/cache": "server-only API",
    "next/og": "server-only API",
    "next/script": "third-party script injection",
    "next/font/local": "needs binary font files; use next/font/google",
    "server-only": "server-only marker",
}
NODE_BUILTINS = frozenset(
    "assert async_hooks buffer child_process cluster crypto dgram dns events fs http http2 https "
    "module net os path perf_hooks process querystring readline stream string_decoder timers tls "
    "tty url util v8 vm worker_threads zlib".split()
)
SERVER_EXPORTS = frozenset(
    "generateStaticParams generateMetadata generateViewport generateImageMetadata "
    "generateSitemaps revalidate dynamic dynamicParams fetchCache runtime preferredRegion "
    "maxDuration".split()
)
APP_ENTRIES = frozenset({"page", "layout", "not-found"})
UNSUPPORTED_CONVENTIONS = frozenset({"loading", "error", "global-error", "template", "default"})
# React's server build exports these hooks; every other `use*` needs a Client Component
SERVER_SAFE_HOOKS = frozenset({"use", "useId", "useMemo", "useCallback", "useDebugValue"})
HOOK = re.compile(r"^use[A-Z]")
EVENT_PROP = re.compile(r"^on[A-Z]")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


@dataclass(frozen=True)
class Import:
    spec: str
    line: int
    names: tuple[str, ...]  # "default" for a default import; empty for namespace or side effect
    type_only: bool


@dataclass
class Module:
    path: str
    tree: Tree
    use_client: bool
    imports: list[Import]
    exports: set[str] | None  # None when `export * from` makes the set unknown

    @property
    def root(self) -> Node:
        return self.tree.root_node


def text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", "replace")


def line_of(node: Node) -> int:
    return node.start_point.row + 1


def walk(node: Node) -> Iterator[Node]:
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def string_value(node: Node | None) -> str | None:
    """Value of a string literal, or of a template literal without substitutions."""
    if node is None:
        return None
    if node.type == "string":
        return "".join(text(c) for c in node.named_children if c.type == "string_fragment")
    if node.type == "template_string" and not any(
        c.type == "template_substitution" for c in node.named_children
    ):
        return text(node)[1:-1]
    return None


def first_error(node: Node) -> Node | None:
    if node.is_error or node.is_missing:
        return node
    if not node.has_error:
        return None
    for child in node.children:
        found = first_error(child)
        if found is not None:
            return found
    return node


def directives(block: Node) -> list[str]:
    """Directive prologue of a program or function body: leading string statements."""
    found: list[str] = []
    for child in block.named_children:
        if child.type == "comment":
            continue
        if child.type == "expression_statement" and child.named_child_count == 1:
            value = string_value(child.named_children[0])
            if value is not None:
                found.append(value)
                continue
        break
    return found


def binding_names(pattern: Node) -> Iterator[str]:
    if pattern.type in ("identifier", "shorthand_property_identifier_pattern"):
        yield text(pattern)
        return
    for index, child in enumerate(pattern.children):
        field = pattern.field_name_for_child(index)
        if field == "right" or (pattern.type == "pair_pattern" and field == "key"):
            continue  # default values and property keys are not bindings
        yield from binding_names(child)


def declared_names(declaration: Node) -> Iterator[str]:
    if declaration.type in ("lexical_declaration", "variable_declaration"):
        for declarator in declaration.named_children:
            if declarator.type == "variable_declarator":
                name = declarator.child_by_field_name("name")
                if name is not None:
                    yield from binding_names(name)
        return
    name = declaration.child_by_field_name("name")
    if name is not None:
        yield text(name)


def extract(tree: Tree) -> tuple[list[Import], set[str] | None]:
    imports: list[Import] = []
    exports: set[str] | None = set()
    for node in walk(tree.root_node):
        if node.type == "import_statement":
            spec = string_value(node.child_by_field_name("source")) or ""
            names: list[str] = []
            typed: list[bool] = []
            for clause in node.named_children:
                if clause.type != "import_clause":
                    continue
                for part in clause.named_children:
                    if part.type == "identifier":
                        names.append("default")
                        typed.append(False)
                    elif part.type == "namespace_import":
                        typed.append(False)
                    elif part.type == "named_imports":
                        for specifier in part.named_children:
                            if specifier.type == "import_specifier":
                                names.append(text(specifier.child_by_field_name("name")))
                                typed.append(any(c.type == "type" for c in specifier.children))
            type_only = any(c.type == "type" for c in node.children) or (bool(typed) and all(typed))
            imports.append(Import(spec, line_of(node), tuple(names), type_only))
        elif node.type == "export_statement":
            source = node.child_by_field_name("source")
            exported: list[str] = []
            if any(c.type == "default" for c in node.children):
                exported.append("default")
            declaration = node.child_by_field_name("declaration")
            if declaration is not None:
                exported.extend(declared_names(declaration))
            reexported: list[str] = []
            star = False
            for part in node.named_children:
                if part.type == "export_clause":
                    for specifier in part.named_children:
                        if specifier.type == "export_specifier":
                            name = text(specifier.child_by_field_name("name"))
                            alias = specifier.child_by_field_name("alias")
                            exported.append(text(alias) if alias is not None else name)
                            reexported.append(name)
                elif part.type == "namespace_export":
                    exported.extend(text(c) for c in part.named_children if c.type == "identifier")
            if source is not None:
                star = any(c.type == "*" for c in node.children)
                type_only = any(c.type == "type" for c in node.children)
                imports.append(
                    Import(string_value(source) or "", line_of(node), tuple(reexported), type_only)
                )
            if star:
                exports = None
            elif exports is not None:
                exports.update(exported)
        elif node.type == "call_expression":
            function = node.child_by_field_name("function")
            arguments = node.child_by_field_name("arguments")
            if function is None or arguments is None or arguments.named_child_count == 0:
                continue
            if function.type == "import" or (
                function.type == "identifier" and text(function) == "require"
            ):
                spec = string_value(arguments.named_children[0])
                if spec is not None:
                    imports.append(Import(spec, line_of(node), (), False))
    return imports, exports


def strip_jsonc(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"(?m)^\s*//.*$", "", source)
    return re.sub(r",(\s*[}\]])", r"\1", source)


def package_name(spec: str) -> str:
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


def suffix(path: str) -> str:
    return posixpath.splitext(path)[1].lower()


def stem(path: str) -> str:
    return posixpath.splitext(posixpath.basename(path))[0]


class Verifier:
    def __init__(self, files: Mapping[str, bytes]) -> None:
        self.files = files
        self.findings: list[Finding] = []
        self.modules: dict[str, Module] = {}
        self.app_dir = "src/app" if any(p.startswith("src/app/") for p in files) else "app"
        self.package: dict[str, Any] = self._json("package.json") or {}
        self.aliases = self._aliases()
        self.image_hosts: list[re.Pattern[str]] = []

    # -- helpers --------------------------------------------------------------------------------

    def add(self, rule: str, path: str, line: int, message: str) -> None:
        finding = Finding(rule, path, line, message)
        if finding not in self.findings:
            self.findings.append(finding)

    def _json(self, path: str) -> dict[str, Any] | None:
        raw = self.files.get(path)
        if raw is None:
            return None
        try:
            data = json.loads(strip_jsonc(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            self.add("config.invalid", path, 1, f"cannot parse {path}: {error}")
            return None
        return data if isinstance(data, dict) else None  # pyright: ignore[reportUnknownVariableType]

    def _aliases(self) -> list[tuple[str, list[str]]]:
        options: dict[str, Any] = (self._json("tsconfig.json") or {}).get("compilerOptions", {})
        base = str(options.get("baseUrl", "."))
        aliases: list[tuple[str, list[str]]] = []
        paths: dict[str, list[str]] = options.get("paths", {})
        for key, targets in paths.items():
            if key.endswith("*"):
                prefixes = [posixpath.join(base, t[:-1]) for t in targets if t.endswith("*")]
                aliases.append((key[:-1], prefixes))
        return aliases

    def in_app(self, path: str) -> bool:
        return path.startswith(self.app_dir + "/")

    def is_entry(self, path: str) -> bool:
        return self.in_app(path) and stem(path) in APP_ENTRIES and suffix(path) in PARSERS

    def resolve(self, importer: str, spec: str) -> tuple[bool, str | None]:
        """(is_local, resolved path). A local import that resolves to nothing gives (True, None)."""
        bases: list[str] = []
        if spec.startswith((".", "/")):
            bases.append(posixpath.join(posixpath.dirname(importer), spec).lstrip("/"))
        else:
            for prefix, targets in self.aliases:
                if spec.startswith(prefix):
                    bases.extend(posixpath.join(t, spec[len(prefix) :]) for t in targets)
            if not bases:
                return False, None
        for base in (posixpath.normpath(b) for b in bases):
            candidates = [base, *(base + e for e in RESOLVE_EXTS)]
            candidates += [f"{base}/index{e}" for e in RESOLVE_EXTS]
            for candidate in candidates:
                if candidate in self.files:
                    return True, candidate
        return True, None

    # -- checks ---------------------------------------------------------------------------------

    def run(self) -> list[Finding]:
        self.check_files()
        self.check_package_json()
        for path in sorted(self.files):
            if suffix(path) in PARSERS and not path.startswith("node_modules/"):
                self.parse(path)
        self.image_hosts = self._image_hosts()
        for module in self.modules.values():
            self.check_module(module)
        self.check_boundary()
        self.check_root_layout()
        return sorted(self.findings, key=lambda f: (f.path, f.line, f.rule))

    def check_files(self) -> None:
        for path, raw in self.files.items():
            if suffix(path) in BINARY_EXTS:
                self.add("file.binary", path, 1, "binary asset in the project; use a remote URL")
            else:
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError:
                    self.add("file.binary", path, 1, "file is not UTF-8 text")
            if suffix(path) not in PARSERS:
                continue
            if stem(path) in ("middleware", "proxy") and posixpath.dirname(path) in ("", "src"):
                self.add("file.forbidden-route", path, 1, "middleware needs a server")
            if not self.in_app(path):
                continue
            if stem(path) == "route":
                self.add("file.forbidden-route", path, 1, "route handlers need a server")
            elif stem(path) in UNSUPPORTED_CONVENTIONS:
                self.add(
                    "file.unsupported-convention",
                    path,
                    1,
                    f"`{stem(path)}` files are not emulated by the preview",
                )
            for segment in path.split("/")[:-1]:
                if segment.startswith("@") or segment.startswith(("(.)", "(..)", "(...)")):
                    self.add(
                        "file.unsupported-convention",
                        path,
                        1,
                        f"segment `{segment}`: parallel and intercepting routes are not emulated",
                    )

    def check_package_json(self) -> None:
        raw = self.files.get("package.json")
        if raw is None:
            self.add("config.invalid", "package.json", 1, "package.json is missing")
            return
        lines = raw.decode("utf-8", "replace").splitlines()
        dependencies: dict[str, str] = self.package.get("dependencies", {})
        for name, version in dependencies.items():
            line = next((i + 1 for i, s in enumerate(lines) if f'"{name}"' in s), 1)
            if name == "next":
                continue
            if name not in VETTED:
                self.add("package.not-vetted", "package.json", line, f"`{name}` is not vetted")
                continue
            pinned, status = VETTED[name]
            if status == "on_hold":
                self.add("package.on-hold", "package.json", line, f"`{name}` is on hold")
            if version != pinned:
                self.add(
                    "package.version",
                    "package.json",
                    line,
                    f"`{name}` must be pinned to {pinned}, not {version}",
                )

    def parse(self, path: str) -> None:
        source = self.files[path]
        tree = PARSERS[suffix(path)].parse(source)
        error = first_error(tree.root_node)
        if error is not None:
            kind = "missing" if error.is_missing else "unexpected"
            self.add("parse.syntax", path, line_of(error), f"syntax error ({kind} `{error.type}`)")
            return  # error recovery makes the rest of the tree unreliable
        imports, exports = extract(tree)
        use_client = "use client" in directives(tree.root_node)
        self.modules[path] = Module(path, tree, use_client, imports, exports)

    def check_module(self, module: Module) -> None:
        path = module.path
        for imp in module.imports:
            self.check_import(module, imp)
        default_export = self.default_export_name(module)
        for node in walk(module.root):
            kind = node.type
            if kind == "jsx_element":
                open_tag, close_tag = (
                    node.child_by_field_name(f) for f in ("open_tag", "close_tag")
                )
                opening = text(open_tag.child_by_field_name("name")) if open_tag else ""
                closing = text(close_tag.child_by_field_name("name")) if close_tag else ""
                if opening != closing:
                    self.add(
                        "parse.jsx-mismatch",
                        path,
                        line_of(node),
                        f"<{opening}> is closed by </{closing}>",
                    )
            elif kind == "expression_statement" and node.named_child_count == 1:
                if string_value(node.named_children[0]) == "use server":
                    self.add(
                        "directive.use-server", path, line_of(node), '"use server" needs a server'
                    )
            elif kind == "export_statement" and self.in_app(path):
                declaration = node.child_by_field_name("declaration")
                names = list(declared_names(declaration)) if declaration is not None else []
                for name in names:
                    if name in SERVER_EXPORTS:
                        self.add(
                            "export.server-feature",
                            path,
                            line_of(node),
                            f"`{name}` is a server feature the preview ignores",
                        )
            elif kind == "call_expression":
                self.check_call(module, node)
            elif kind == "member_expression" and text(node) == "process.env":
                parent = node.parent
                variable = (
                    text(parent.child_by_field_name("property"))
                    if parent is not None and parent.type == "member_expression"
                    else ""
                )
                if variable != "NODE_ENV":
                    self.add(
                        "env.process",
                        path,
                        line_of(node),
                        f"`process.env.{variable or '…'}`: no environment in the preview",
                    )
            elif kind in ("function_declaration", "function_expression", "arrow_function"):
                self.check_async_component(module, node, default_export)
            elif kind in ("jsx_opening_element", "jsx_self_closing_element"):
                self.check_jsx_element(module, node)

    def check_import(self, module: Module, imp: Import) -> None:
        path, spec = module.path, imp.spec
        if suffix(spec) in ASSET_EXTS:
            self.add("module.static-asset", path, imp.line, f"static asset import `{spec}`")
            return
        is_local, target = self.resolve(path, spec)
        if is_local:
            if target is None:
                self.add("import.unresolved", path, imp.line, f"cannot resolve `{spec}`")
                return
            exporter = self.modules.get(target)
            if exporter is None or exporter.exports is None:
                return
            for name in imp.names:
                if name not in exporter.exports:
                    what = "a default export" if name == "default" else f"an export `{name}`"
                    self.add("import.missing-export", path, imp.line, f"`{spec}` has no {what}")
            return
        if imp.type_only:
            return
        bare = spec.removeprefix("node:")
        if spec in FORBIDDEN_MODULES:
            self.add("module.forbidden", path, imp.line, f"`{spec}`: {FORBIDDEN_MODULES[spec]}")
        elif spec.startswith("node:") or package_name(bare) in NODE_BUILTINS:
            self.add("module.forbidden", path, imp.line, f"`{spec}`: Node built-in module")
        elif package_name(spec) == "next":
            if spec not in NEXT_SHIMMED:
                self.add("module.forbidden", path, imp.line, f"`{spec}` is not in the preview")
        elif package_name(spec) not in self.package.get("dependencies", {}):
            self.add(
                "package.undeclared",
                path,
                imp.line,
                f"`{package_name(spec)}` is not in package.json dependencies",
            )

    def check_call(self, module: Module, node: Node) -> None:
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is None or arguments is None:
            return
        if text(function) == "fetch" and arguments.named_child_count:
            url = string_value(arguments.named_children[0])
            if url is not None and url.startswith("/"):
                self.add(
                    "fetch.own-api", module.path, line_of(node), f"`fetch('{url}')`: no API routes"
                )

    def check_async_component(self, module: Module, node: Node, default_export: str) -> None:
        if not any(c.type == "async" for c in node.children):
            return
        body = node.child_by_field_name("body")
        if body is None or not any(n.type.startswith("jsx_") for n in walk(body)):
            return
        if self.is_entry(module.path):
            parent = node.parent
            if parent is not None and parent.type == "export_statement":
                return
            if text(node.child_by_field_name("name")) == default_export:
                return
        self.add(
            "component.nested-async",
            module.path,
            line_of(node),
            "async component outside a page or layout",
        )

    def check_jsx_element(self, module: Module, node: Node) -> None:
        tag = text(node.child_by_field_name("name"))
        attributes = {
            text(a.named_children[0]): a.named_children[-1] if a.named_child_count > 1 else None
            for a in node.named_children
            if a.type == "jsx_attribute"
        }
        if tag == "Environment" and ("preset" in attributes or "files" in attributes):
            self.add(
                "three.environment-preset",
                module.path,
                line_of(node),
                "<Environment preset|files> downloads assets from a third-party CDN",
            )
        if tag in self.image_components(module) and (value := attributes.get("src")) is not None:
            if value.type == "jsx_expression" and value.named_child_count:
                value = value.named_children[0]
            src = string_value(value)
            if src is None:
                return  # computed src: only the real build can check it
            host = urlparse(src).hostname if src.startswith(("http://", "https://")) else None
            if host is None:
                self.add("image.src", module.path, line_of(node), f"`{src}` is not a remote URL")
            elif not any(p.fullmatch(host) for p in self.image_hosts):
                self.add(
                    "image.src",
                    module.path,
                    line_of(node),
                    f"host `{host}` is not in next.config images.remotePatterns",
                )

    @staticmethod
    def image_components(module: Module) -> set[str]:
        names: set[str] = set()
        for node in module.root.named_children:
            if node.type == "import_statement" and (
                string_value(node.child_by_field_name("source")) == "next/image"
            ):
                for clause in node.named_children:
                    names.update(text(c) for c in clause.named_children if c.type == "identifier")
        return names

    def _image_hosts(self) -> list[re.Pattern[str]]:
        """Host patterns from next.config `remotePatterns[].hostname` and `domains`."""
        hosts: list[str] = []
        for path, module in self.modules.items():
            if stem(path) != "next.config" or "/" in path:
                continue
            for node in walk(module.root):
                if node.type != "pair":
                    continue
                key, value = (
                    text(node.child_by_field_name("key")),
                    node.child_by_field_name("value"),
                )
                if key == "hostname" and (host := string_value(value)) is not None:
                    hosts.append(host)
                elif key == "domains" and value is not None:
                    hosts.extend(s for c in value.named_children if (s := string_value(c)))
        patterns: list[re.Pattern[str]] = []
        for host in hosts:
            escaped = re.escape(host).replace(r"\*\*", ".*").replace(r"\*", "[^.]*")
            patterns.append(re.compile(escaped))
        return patterns

    @staticmethod
    def default_export_name(module: Module) -> str:
        for node in module.root.named_children:
            if node.type == "export_statement" and any(c.type == "default" for c in node.children):
                value = node.child_by_field_name("value")
                if value is not None and value.type == "identifier":
                    return text(value)
        return ""

    # -- Server/Client Component boundary -------------------------------------------------------

    def check_boundary(self) -> None:
        """Modules reachable from app entries without crossing "use client" are Server Components."""
        queue = deque(sorted(p for p in self.modules if self.is_entry(p)))
        server: set[str] = set()
        while queue:
            path = queue.popleft()
            module = self.modules.get(path)
            if path in server or module is None or module.use_client:
                continue
            server.add(path)
            for imp in module.imports:
                if not imp.type_only:
                    _, target = self.resolve(path, imp.spec)
                    if target is not None:
                        queue.append(target)
        for path in sorted(server):
            self.check_server_module(self.modules[path])

    def check_server_module(self, module: Module) -> None:
        path = module.path
        client_components = self.client_component_names(module)
        for node in walk(module.root):
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                if function is None:
                    continue
                name = text(
                    function.child_by_field_name("property")
                    if function.type == "member_expression"
                    else function
                )
                if (HOOK.match(name) and name not in SERVER_SAFE_HOOKS) or name == "createContext":
                    self.add(
                        "client.boundary",
                        path,
                        line_of(node),
                        f'`{name}` in a Server Component; add "use client" to this file',
                    )
                elif name == "dynamic" and self.ssr_false(node):
                    self.add(
                        "client.dynamic-ssr-false",
                        path,
                        line_of(node),
                        "`ssr: false` is not allowed in a Server Component; move it to a "
                        '"use client" file',
                    )
            elif node.type in ("jsx_opening_element", "jsx_self_closing_element"):
                tag = text(node.child_by_field_name("name"))
                for attribute in node.named_children:
                    if attribute.type != "jsx_attribute":
                        continue
                    prop = text(attribute.named_children[0])
                    value = (
                        attribute.named_children[-1] if attribute.named_child_count > 1 else None
                    )
                    passes_function = value is not None and any(
                        c.type in ("arrow_function", "function_expression")
                        for c in value.named_children
                    )
                    if tag[:1].islower() and EVENT_PROP.match(prop):
                        self.add(
                            "client.boundary",
                            path,
                            line_of(attribute),
                            f'`{prop}` on <{tag}> in a Server Component; add "use client"',
                        )
                    elif tag in client_components and passes_function:
                        self.add(
                            "client.boundary",
                            path,
                            line_of(attribute),
                            f"function passed as `{prop}` from a Server Component to <{tag}>",
                        )

    def client_component_names(self, module: Module) -> set[str]:
        """Local names this module imports from "use client" modules."""
        names: set[str] = set()
        for node in module.root.named_children:
            if node.type != "import_statement":
                continue
            _, target = self.resolve(
                module.path, string_value(node.child_by_field_name("source")) or ""
            )
            if target is None or not (m := self.modules.get(target)) or not m.use_client:
                continue
            for part in walk(node):
                if part.type == "import_specifier":
                    alias = part.child_by_field_name("alias") or part.child_by_field_name("name")
                    names.add(text(alias))
                elif (
                    part.type == "identifier"
                    and part.parent
                    and part.parent.type == "import_clause"
                ):
                    names.add(text(part))
        return names

    @staticmethod
    def ssr_false(call: Node) -> bool:
        for node in walk(call):
            if node.type == "pair":
                key, value = node.child_by_field_name("key"), node.child_by_field_name("value")
                if text(key) == "ssr" and text(value) == "false":
                    return True
        return False

    # -- project shape --------------------------------------------------------------------------

    def check_root_layout(self) -> None:
        candidates = (f"{self.app_dir}/layout{e}" for e in (".tsx", ".jsx", ".js"))
        layout = next((c for c in candidates if c in self.files), None)
        if layout is None:
            self.add("layout.root-html", f"{self.app_dir}/layout.tsx", 1, "root layout is missing")
            return
        module = self.modules.get(layout)
        if module is None:
            return
        tags = {
            text(n.child_by_field_name("name"))
            for n in walk(module.root)
            if n.type in ("jsx_opening_element", "jsx_self_closing_element")
        }
        for tag in ("html", "body"):
            if tag not in tags:
                self.add("layout.root-html", layout, 1, f"root layout must render <{tag}>")


def verify(files: Mapping[str, bytes]) -> list[Finding]:
    return Verifier(files).run()


def load_project(root: Path) -> dict[str, bytes]:
    skip = {"node_modules", ".next", ".git"}
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not skip.intersection(p.relative_to(root).parts)
    }


def main() -> None:
    findings = verify(load_project(Path(sys.argv[1])))
    for finding in findings:
        print(finding)
    print(f"{len(findings)} finding(s)")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
