// Turns a frontend-only Next.js App Router project into a Sandpack classic ("react-ts") sandbox:
// - `next` and `server-only` come from shims in a fake node_modules, so the agent's imports are
//   untouched and the exported project stays a real Next.js project;
// - a hidden entry builds the route table from app/**/page.tsx and the layouts above each page;
// - Tailwind v4 CSS is moved into a <style type="text/tailwindcss"> for the Tailwind browser build.
import type { SandpackBundlerFiles } from "@codesandbox/sandpack-client";

export type Project = Record<string, string>; // path relative to the project root -> source

export interface RouteInfo {
  path: string; // e.g. /blog/[slug]
  page: string; // e.g. /app/blog/[slug]/page.tsx
  layouts: string[];
}

export interface Translation {
  files: SandpackBundlerFiles;
  entry: string;
  dependencies: Record<string, string>;
  externalResources: string[];
  routes: RouteInfo[];
  notes: string[];
}

export const TAILWIND_BROWSER = "https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.3.3";
const MODERN_SCREENSHOT_VERSION = "4.7.0";
const ENTRY = "/__catronaut/entry.tsx";
const PAGE_RE = /^page\.(tsx|jsx|ts|js)$/;
const LAYOUT_RE = /^layout\.(tsx|jsx|ts|js)$/;
const NOT_FOUND_RE = /^not-found\.(tsx|jsx|ts|js)$/;
const IGNORED_RE = /^(route|loading|error|global-error|template|default|middleware)\.(tsx|jsx|ts|js)$/;
const TAILWIND_IMPORT_RE = /^\s*@import\s+["']tailwindcss["'];?\s*$/m;
const SERVER_ONLY_NEXT_MODULES = ["headers", "server", "cache", "og", "script"];

const shimSources = import.meta.glob("./shims/**/*", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;
const bridgeSource = import.meta.glob("./sandbox/bridge.js", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

function shimFiles(): SandpackBundlerFiles {
  const files: SandpackBundlerFiles = {};
  for (const [path, code] of Object.entries(shimSources)) {
    files[path.replace("./shims/", "/node_modules/")] = { code, hidden: true };
  }
  for (const name of SERVER_ONLY_NEXT_MODULES) {
    files[`/node_modules/next/${name}.js`] = {
      code: `throw new Error("[preview contract] 'next/${name}' is not available in the preview (frontend-only subset).");\n`,
      hidden: true,
    };
  }
  return files;
}

function stripExtension(path: string): string {
  return path.replace(/\.(tsx|jsx|ts|js)$/, "");
}

function routePath(dirSegments: string[]): string {
  const visible = dirSegments.filter((s) => !(s.startsWith("(") && s.endsWith(")")));
  return "/" + visible.join("/");
}

function segmentLiteral(segment: string): string {
  const optionalCatchAll = /^\[\[\.\.\.(.+)\]\]$/.exec(segment);
  if (optionalCatchAll) return `{kind:"catchall",name:${JSON.stringify(optionalCatchAll[1])},optional:true}`;
  const catchAll = /^\[\.\.\.(.+)\]$/.exec(segment);
  if (catchAll) return `{kind:"catchall",name:${JSON.stringify(catchAll[1])},optional:false}`;
  const dynamic = /^\[(.+)\]$/.exec(segment);
  if (dynamic) return `{kind:"dynamic",name:${JSON.stringify(dynamic[1])}}`;
  return `{kind:"static",value:${JSON.stringify(segment)}}`;
}

export function translate(project: Project): Translation {
  const notes: string[] = [];
  const files: SandpackBundlerFiles = {};
  let tailwindSource = "";

  for (const [rawPath, code] of Object.entries(project)) {
    const path = "/" + rawPath.replace(/^\/+/, "");
    if (path.endsWith(".css") && TAILWIND_IMPORT_RE.test(code)) {
      tailwindSource += code.replace(TAILWIND_IMPORT_RE, "") + "\n";
      files[path] = { code: "/* moved to <style type=\"text/tailwindcss\"> by the preview */\n" };
      continue;
    }
    files[path] = { code };
  }

  const appDir = Object.keys(files).some((p) => p.startsWith("/src/app/")) ? "/src/app" : "/app";
  const appFiles = Object.keys(files).filter((p) => p.startsWith(appDir + "/"));
  const layoutsByDir = new Map<string, string>();
  const pages: string[] = [];
  let notFound: string | null = null;
  for (const file of appFiles) {
    const name = file.slice(file.lastIndexOf("/") + 1);
    const dir = file.slice(0, file.lastIndexOf("/"));
    if (PAGE_RE.test(name)) pages.push(file);
    else if (LAYOUT_RE.test(name)) layoutsByDir.set(dir, file);
    else if (NOT_FOUND_RE.test(name) && dir === appDir) notFound = file;
    else if (IGNORED_RE.test(name)) notes.push(`ignored by the preview: ${file}`);
  }

  const imports: string[] = [];
  const moduleIds = new Map<string, string>();
  const idFor = (file: string): string => {
    let id = moduleIds.get(file);
    if (!id) {
      id = `M${moduleIds.size}`;
      moduleIds.set(file, id);
      imports.push(`import * as ${id} from ${JSON.stringify(".." + stripExtension(file))};`);
    }
    return id;
  };

  const routes: RouteInfo[] = [];
  const routeLiterals: string[] = [];
  for (const page of pages.sort()) {
    const dir = page.slice(0, page.lastIndexOf("/"));
    const dirSegments = dir.slice(appDir.length).split("/").filter(Boolean);
    const layouts: string[] = [];
    for (let i = 0; i <= dirSegments.length; i++) {
      const layout = layoutsByDir.get([appDir, ...dirSegments.slice(0, i)].join("/"));
      if (layout) layouts.push(layout);
    }
    const visible = dirSegments.filter((s) => !(s.startsWith("(") && s.endsWith(")")));
    const path = routePath(dirSegments);
    routes.push({ path, page, layouts });
    routeLiterals.push(
      `{id:${JSON.stringify(path)},segments:[${visible.map(segmentLiteral).join(",")}],` +
        `page:${idFor(page)},layouts:[${layouts.map(idFor).join(",")}]}`,
    );
  }
  const rootLayout = layoutsByDir.get(appDir);
  const rootLayoutId = rootLayout ? idFor(rootLayout) : "null";
  const notFoundId = notFound ? idFor(notFound) : "null";

  const entryCode = [
    `import { reportRendered, reportError } from "./bridge";`,
    `import { mount } from "next/dist/catronaut/runtime";`,
    ...imports,
    `const tailwind = document.createElement("style");`,
    `tailwind.setAttribute("type", "text/tailwindcss");`,
    `tailwind.textContent = ${JSON.stringify(tailwindSource)};`,
    `document.head.appendChild(tailwind);`,
    `mount({`,
    `  routes: [${routeLiterals.join(",\n    ")}],`,
    `  rootLayout: ${rootLayoutId},`,
    `  notFound: ${notFoundId},`,
    `  onRendered: reportRendered,`,
    `  onError: reportError,`,
    `});`,
    ``,
  ].join("\n");

  Object.assign(files, shimFiles());
  files[ENTRY] = { code: entryCode, hidden: true };
  files["/__catronaut/bridge.js"] = { code: Object.values(bridgeSource)[0] ?? "", hidden: true };

  const pkg = JSON.parse(project["package.json"] ?? "{}") as { dependencies?: Record<string, string> };
  const dependencies: Record<string, string> = { ...(pkg.dependencies ?? {}) };
  for (const name of ["next", "server-only"]) {
    if (dependencies[name]) {
      delete dependencies[name];
      notes.push(`dependency '${name}' served by the preview shim`);
    }
  }
  dependencies["modern-screenshot"] = MODERN_SCREENSHOT_VERSION;
  files["/package.json"] = {
    code: JSON.stringify({ name: "preview", main: ENTRY, dependencies }, null, 2),
    hidden: true,
  };
  files["/public/index.html"] = {
    code: '<!doctype html>\n<html lang="en"><head><meta charset="UTF-8"></head><body><div id="root"></div></body></html>\n',
    hidden: true,
  };

  return {
    files,
    entry: ENTRY,
    dependencies,
    externalResources: tailwindSource ? [TAILWIND_BROWSER] : [],
    routes,
    notes,
  };
}
