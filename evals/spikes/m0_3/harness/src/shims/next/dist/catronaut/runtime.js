// Preview runtime: App Router emulation. The generated entry calls mount() with a route table built
// from app/**/page.tsx and the layouts above each page.
var React = require("react");
var ReactDOMClient = require("react-dom/client");
var router = require("./router");

var h = React.createElement;

// --- matching ------------------------------------------------------------------------------

function segmentRank(segment) {
  if (segment.kind === "static") return 0;
  if (segment.kind === "dynamic") return 1;
  return 2;
}

function compareRoutes(a, b) {
  var length = Math.max(a.segments.length, b.segments.length);
  for (var i = 0; i < length; i++) {
    var sa = a.segments[i];
    var sb = b.segments[i];
    if (!sa) return -1;
    if (!sb) return 1;
    var diff = segmentRank(sa) - segmentRank(sb);
    if (diff) return diff;
  }
  return 0;
}

function matchRoute(route, parts) {
  var params = {};
  for (var i = 0; i < route.segments.length; i++) {
    var segment = route.segments[i];
    if (segment.kind === "catchall") {
      var rest = parts.slice(i);
      if (!rest.length && !segment.optional) return null;
      if (rest.length) params[segment.name] = rest;
      return params;
    }
    var part = parts[i];
    if (part === undefined) return null;
    if (segment.kind === "static" && segment.value !== part) return null;
    if (segment.kind === "dynamic") params[segment.name] = part;
  }
  return parts.length === route.segments.length ? params : null;
}

function findRoute(routes, pathname) {
  var parts = pathname
    .split("/")
    .filter(Boolean)
    .map(function (part) {
      return decodeURIComponent(part);
    });
  for (var i = 0; i < routes.length; i++) {
    var params = matchRoute(routes[i], parts);
    if (params) return { route: routes[i], params: params };
  }
  return null;
}

// --- params as a settled promise ----------------------------------------------------------
// Next.js 15+ passes `params` and `searchParams` as promises. A pre-settled, cached thenable lets
// `use(params)` read it synchronously instead of suspending on a fresh promise every render.

var settled = new Map();

function settledPromise(key, value) {
  if (!settled.has(key)) {
    var promise = Promise.resolve(value);
    promise.status = "fulfilled";
    promise.value = value;
    settled.set(key, promise);
  }
  return settled.get(key);
}

// --- async server components (page and layouts only) -------------------------------------

var asyncResults = new Map();

function ComponentHost(props) {
  var cached = asyncResults.get(props.cacheKey);
  if (cached) return React.use(cached);
  var output = props.component(props.componentProps);
  if (output && typeof output.then === "function") {
    asyncResults.set(props.cacheKey, output);
    return React.use(output);
  }
  return output;
}

// --- metadata ------------------------------------------------------------------------------

function resolveMetadata(modules) {
  var template = null;
  var title = null;
  var description = null;
  modules.forEach(function (mod) {
    var meta = mod && mod.metadata;
    if (!meta) return;
    if (meta.description) description = meta.description;
    var t = meta.title;
    if (typeof t === "string") {
      title = template ? template.replace("%s", t) : t;
    } else if (t && typeof t === "object") {
      if (t.absolute) title = t.absolute;
      else if (t.default) title = t.default;
      if (t.template) template = t.template;
    }
  });
  return { title: title, description: description };
}

// --- boundaries ----------------------------------------------------------------------------

function digestOf(error) {
  return error && typeof error.digest === "string" ? error.digest : "";
}

var RouteBoundary = (function () {
  function RouteBoundary(props) {
    React.Component.call(this, props);
    this.state = { error: null };
  }
  RouteBoundary.prototype = Object.create(React.Component.prototype);
  RouteBoundary.prototype.constructor = RouteBoundary;
  RouteBoundary.getDerivedStateFromError = function (error) {
    return { error: error };
  };
  RouteBoundary.prototype.componentDidCatch = function (error, info) {
    var digest = digestOf(error);
    if (digest.indexOf("NEXT_REDIRECT;") === 0) {
      var target = digest.slice("NEXT_REDIRECT;".length);
      setTimeout(function () {
        router.navigate(target, { replace: true });
      }, 0);
      return;
    }
    if (digest === "NEXT_NOT_FOUND") return;
    this.props.onError("render", error, info && info.componentStack);
  };
  RouteBoundary.prototype.componentDidUpdate = function (prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  };
  RouteBoundary.prototype.render = function () {
    var error = this.state.error;
    if (!error) return this.props.children;
    var digest = digestOf(error);
    if (digest === "NEXT_NOT_FOUND") return this.props.notFound;
    // The outermost boundary renders straight into `document`, where only <html> is valid.
    if (digest.indexOf("NEXT_REDIRECT;") === 0 || this.props.bare) return null;
    return h(
      "pre",
      { "data-catronaut-error": "", style: { color: "#b00020", whiteSpace: "pre-wrap", padding: 16 } },
      String(error && error.stack ? error.stack : error),
    );
  };
  return RouteBoundary;
})();

// --- app -----------------------------------------------------------------------------------

function renderChain(layouts, leaf, keyPrefix, params) {
  var element = leaf;
  for (var i = layouts.length - 1; i >= 0; i--) {
    element = h(ComponentHost, {
      key: keyPrefix + ":layout:" + i,
      cacheKey: keyPrefix + ":layout:" + i,
      component: layouts[i].default,
      componentProps: { children: element, params: params },
    });
  }
  return element;
}

function App(props) {
  var config = props.config;
  var location = React.useSyncExternalStore(router.subscribe, router.getSnapshot);
  var pathname = location.split("?")[0];
  var search = location.split("?")[1] || "";
  var found = findRoute(config.routes, pathname);

  React.useEffect(
    function () {
      config.onRendered({ pathname: pathname, matched: Boolean(found) });
    },
    [location],
  );

  var notFoundElement = config.notFound ? h(config.notFound.default) : h("h1", null, "404");

  if (!found) {
    var rootLayouts = config.rootLayout ? [config.rootLayout] : [];
    return renderChain(rootLayouts, notFoundElement, "404", settledPromise("404", {}));
  }

  var route = found.route;
  var paramsKey = route.id + JSON.stringify(found.params);
  var params = settledPromise("p:" + paramsKey, found.params);
  var searchParams = settledPromise("s:" + search, Object.fromEntries(new URLSearchParams(search)));
  var meta = resolveMetadata(route.layouts.concat([route.page]));

  var page = h(ComponentHost, {
    key: route.id,
    cacheKey: "page:" + paramsKey + "?" + search,
    component: route.page.default,
    componentProps: { params: params, searchParams: searchParams },
  });
  var bounded = h(
    RouteBoundary,
    { resetKey: location, notFound: notFoundElement, onError: config.onError },
    page,
    meta.title ? h("title", null, meta.title) : null,
    meta.description ? h("meta", { name: "description", content: meta.description }) : null,
  );
  return h(
    router.ParamsContext.Provider,
    { value: found.params },
    renderChain(route.layouts, bounded, route.id, params),
  );
}

function mount(config) {
  config.routes.sort(compareRoutes);
  var root = ReactDOMClient.createRoot(document, {
    // notFound() and redirect() are control flow, not errors: keep them out of the console
    onCaughtError: function (error) {
      var digest = digestOf(error);
      if (digest === "NEXT_NOT_FOUND" || digest.indexOf("NEXT_REDIRECT;") === 0) return;
      console.error(error);
    },
    onUncaughtError: function (error, info) {
      config.onError("uncaught", error, info && info.componentStack);
    },
  });
  root.render(
    h(
      RouteBoundary,
      { resetKey: "root", notFound: null, onError: config.onError, bare: true },
      h(React.Suspense, { fallback: null }, h(App, { config: config })),
    ),
  );
}

module.exports = { mount: mount };
