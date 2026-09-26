// Preview shim: client-side router state shared by next/link, next/navigation and the runtime.
var React = require("react");

var listeners = new Set();
function read() {
  return window.location.pathname + window.location.search;
}
var current = read();

function emit() {
  current = read();
  listeners.forEach(function (listener) {
    listener();
  });
}
window.addEventListener("popstate", emit);

function subscribe(listener) {
  listeners.add(listener);
  return function () {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return current;
}

function navigate(href, options) {
  var opts = options || {};
  var url = new URL(href, window.location.href);
  if (url.origin !== window.location.origin) {
    window.location.assign(url.href);
    return;
  }
  var target = url.pathname + url.search + url.hash;
  if (opts.replace) window.history.replaceState(null, "", target);
  else window.history.pushState(null, "", target);
  emit();
  if (opts.scroll !== false) window.scrollTo(0, 0);
}

var ParamsContext = React.createContext({});

window.__catronautRouter = { navigate: navigate };

module.exports = {
  subscribe: subscribe,
  getSnapshot: getSnapshot,
  navigate: navigate,
  refresh: emit,
  ParamsContext: ParamsContext,
};
