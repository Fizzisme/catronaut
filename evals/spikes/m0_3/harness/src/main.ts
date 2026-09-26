// Host page: loads a fixture into Sandpack and records what happens, for run_fixtures.py.
// URL: ?fixture=<name>&bundler=<url, empty = CodeSandbox-hosted>
import { loadSandpackClient, type SandpackMessage } from "@codesandbox/sandpack-client";
import { fixtureNames, loadFixture } from "./fixtures";
import { translate, type RouteInfo } from "./translate";

interface PreviewError {
  source: "bundler" | "runtime" | "console" | "harness";
  kind: string;
  message: string;
  path?: string;
  line?: number;
  stack?: string;
  at: number;
}

interface ScreenshotResult {
  dataUrl?: string;
  error?: string;
  ms: number;
}

interface PreviewState {
  fixture: string;
  bundlerURL: string;
  status: "loading" | "compiled" | "rendered" | "failed";
  compilationError: boolean | null;
  timings: Record<string, number>; // ms since page start
  statuses: { status: string; at: number }[];
  renders: { pathname: string; matched: boolean; title: string; at: number }[];
  errors: PreviewError[];
  routes: RouteInfo[];
  notes: string[];
}

declare global {
  interface Window {
    __preview: {
      state: PreviewState;
      fixtures: string[];
      screenshot: () => Promise<ScreenshotResult>;
    };
  }
}

const params = new URLSearchParams(window.location.search);
const fixture = params.get("fixture") ?? "starter";
const bundlerURL = params.get("bundler") ?? "";
const iframe = document.getElementById("preview") as HTMLIFrameElement;
const bar = document.getElementById("bar") as HTMLDivElement;
const now = (): number => Math.round(performance.now());

const state: PreviewState = {
  fixture,
  bundlerURL: bundlerURL || "hosted",
  status: "loading",
  compilationError: null,
  timings: {},
  statuses: [],
  renders: [],
  errors: [],
  routes: [],
  notes: [],
};

const pendingShots = new Map<string, (result: ScreenshotResult) => void>();

window.__preview = {
  state,
  fixtures: fixtureNames(),
  screenshot: () =>
    new Promise((resolve) => {
      const id = Math.random().toString(36).slice(2);
      pendingShots.set(id, resolve);
      iframe.contentWindow?.postMessage({ catronaut: true, type: "screenshot-request", id }, "*");
      setTimeout(() => {
        if (pendingShots.delete(id)) resolve({ error: "timeout", ms: 30000 });
      }, 30000);
    }),
};

function render(): void {
  bar.textContent = `${fixture} · ${state.bundlerURL} · ${state.status} · errors: ${state.errors.length}`;
}

function onSandpackMessage(msg: SandpackMessage): void {
  const at = now();
  switch (msg.type) {
    case "start":
      state.timings.start ??= at;
      break;
    case "status":
      state.statuses.push({ status: msg.status, at });
      break;
    case "done":
      state.timings.done ??= at;
      state.compilationError = msg.compilatonError;
      if (state.status === "loading") state.status = msg.compilatonError ? "failed" : "compiled";
      break;
    case "action":
      if (msg.action === "show-error") {
        state.errors.push({
          source: "bundler",
          kind: msg.title,
          message: msg.message,
          path: msg.path,
          line: msg.line,
          at,
        });
        state.status = "failed";
      } else if (msg.action === "notification") {
        state.errors.push({ source: "bundler", kind: "notification", message: msg.title, at });
      }
      break;
    case "console":
      for (const entry of msg.log) {
        if (entry.method === "error") {
          state.errors.push({ source: "console", kind: "console.error", message: entry.data.join(" "), at });
        }
      }
      break;
    default:
      break;
  }
  render();
}

window.addEventListener("message", (event: MessageEvent) => {
  if (event.source !== iframe.contentWindow) return;
  const data = event.data as Record<string, unknown> | null;
  if (!data || data.catronaut !== true) return;
  const at = now();
  if (data.type === "rendered") {
    state.renders.push({
      pathname: String(data.pathname),
      matched: Boolean(data.matched),
      title: String(data.title),
      at,
    });
    state.timings.firstRender ??= at;
    if (state.status !== "failed") state.status = "rendered";
  } else if (data.type === "runtime-error") {
    state.errors.push({
      source: "runtime",
      kind: String(data.kind),
      message: String(data.message),
      stack: String(data.stack ?? ""),
      at,
    });
  } else if (data.type === "screenshot") {
    const resolve = pendingShots.get(String(data.id));
    if (resolve) {
      pendingShots.delete(String(data.id));
      resolve({
        dataUrl: typeof data.dataUrl === "string" ? data.dataUrl : undefined,
        error: typeof data.error === "string" ? data.error : undefined,
        ms: Number(data.ms),
      });
    }
  }
  render();
});

async function main(): Promise<void> {
  const translation = translate(loadFixture(fixture));
  state.routes = translation.routes;
  state.notes = translation.notes;
  state.timings.translated = now();
  const client = await loadSandpackClient(
    iframe,
    {
      files: translation.files,
      entry: translation.entry,
      dependencies: translation.dependencies,
      template: "create-react-app-typescript",
    },
    {
      bundlerURL: bundlerURL || undefined,
      externalResources: translation.externalResources,
      showOpenInCodeSandbox: false,
    },
  );
  state.timings.clientLoaded = now();
  client.listen(onSandpackMessage);
}

main().catch((error: unknown) => {
  state.errors.push({ source: "harness", kind: "harness", message: String(error), at: now() });
  state.status = "failed";
  render();
});
render();
