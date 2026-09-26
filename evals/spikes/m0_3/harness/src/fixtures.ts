// Fixture projects under ../fixtures/<name>/. A fixture may overlay another one through
// fixture.json: { "base": "starter", "remove": [...], "dependencies": {...} }.
import type { Project } from "./translate";

interface FixtureManifest {
  base?: string;
  remove?: string[];
  dependencies?: Record<string, string>;
}

const raw = import.meta.glob("../../fixtures/**/*", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const PREFIX = "../../fixtures/";

function ownFiles(name: string): Project {
  const files: Project = {};
  for (const [path, code] of Object.entries(raw)) {
    if (path.startsWith(`${PREFIX}${name}/`)) files[path.slice(PREFIX.length + name.length + 1)] = code;
  }
  return files;
}

export function fixtureNames(): string[] {
  const names = new Set<string>();
  for (const path of Object.keys(raw)) {
    const rest = path.slice(PREFIX.length).split("/");
    // fixtures/<name>/... or fixtures/<group>/<name>/fixture.json
    if (rest[rest.length - 1] === "fixture.json") names.add(rest.slice(0, -1).join("/"));
    else if (rest[1] === "package.json" && rest.length === 2) names.add(rest[0]);
  }
  return [...names].sort();
}

export function loadFixture(name: string): Project {
  const own = ownFiles(name);
  const manifestSource = own["fixture.json"];
  delete own["fixture.json"];
  if (!manifestSource) {
    if (!Object.keys(own).length) throw new Error(`unknown fixture: ${name}`);
    return own;
  }
  const manifest = JSON.parse(manifestSource) as FixtureManifest;
  const project: Project = manifest.base ? loadFixture(manifest.base) : {};
  for (const path of manifest.remove ?? []) delete project[path];
  Object.assign(project, own);
  if (manifest.dependencies) {
    const pkg = JSON.parse(project["package.json"] ?? "{}") as { dependencies?: Record<string, string> };
    pkg.dependencies = { ...(pkg.dependencies ?? {}), ...manifest.dependencies };
    project["package.json"] = JSON.stringify(pkg, null, 2);
  }
  return project;
}
