// Runs inside the preview iframe (imported first by the generated entry). Reports runtime errors and
// render events to the host page and answers screenshot requests. The host only trusts messages
// whose event.source is this iframe; this side only answers its parent window.
import { domToPng } from "modern-screenshot";

// The bundler resolves packages through their CommonJS entry, and its `process` polyfill has no
// emitWarning; three >= 0.18x calls it from build/three.cjs and crashes on import without this.
if (typeof process !== "undefined" && typeof process.emitWarning !== "function") {
  process.emitWarning = function (warning) {
    console.warn(String(warning));
  };
}

function post(message) {
  window.parent.postMessage(Object.assign({ catronaut: true }, message), "*");
}

function describe(error) {
  if (error instanceof Error) return { message: error.message, stack: error.stack || "" };
  return { message: String(error), stack: "" };
}

window.addEventListener("error", function (event) {
  var detail = describe(event.error || event.message);
  post({
    type: "runtime-error",
    kind: "window.error",
    message: detail.message,
    stack: detail.stack,
    source: event.filename || "",
    line: event.lineno || 0,
    column: event.colno || 0,
  });
});

window.addEventListener("unhandledrejection", function (event) {
  var detail = describe(event.reason);
  post({ type: "runtime-error", kind: "unhandledrejection", message: detail.message, stack: detail.stack });
});

window.addEventListener("message", function (event) {
  if (event.source !== window.parent || !event.data || !event.data.catronaut) return;
  if (event.data.type !== "screenshot-request") return;
  var id = event.data.id;
  var started = performance.now();
  // a page shorter than the viewport leaves transparent pixels: paint them with the page background
  var background = getComputedStyle(document.body).backgroundColor;
  domToPng(document.documentElement, {
    width: window.innerWidth,
    height: window.innerHeight,
    scale: 1,
    backgroundColor: background,
  })
    .then(function (dataUrl) {
      post({ type: "screenshot", id: id, dataUrl: dataUrl, ms: performance.now() - started });
    })
    .catch(function (error) {
      post({ type: "screenshot", id: id, error: describe(error).message, ms: performance.now() - started });
    });
});

export function reportRendered(info) {
  post({ type: "rendered", pathname: info.pathname, matched: info.matched, title: document.title });
}

export function reportError(kind, error, componentStack) {
  var detail = describe(error);
  post({
    type: "runtime-error",
    kind: "react." + kind,
    message: detail.message,
    stack: detail.stack,
    componentStack: componentStack || "",
  });
}
