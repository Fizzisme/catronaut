// Preview shim for next/font/google: loads the family from the Google Fonts CSS API at runtime and
// returns the same { className, variable, style } shape as Next.js.
var injected = {};

function addStyle(css) {
  var style = document.createElement("style");
  style.setAttribute("data-catronaut-font", "");
  style.textContent = css;
  document.head.appendChild(style);
}

function addLink(href) {
  var link = document.createElement("link");
  link.rel = "stylesheet";
  // CORS mode makes the @font-face rules readable, so in-iframe screenshots can embed the font
  link.crossOrigin = "anonymous";
  link.href = href;
  document.head.appendChild(link);
}

function toList(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function loadFamily(family, opts) {
  var base = "https://fonts.googleapis.com/css2?family=" + family.replace(/ /g, "+");
  var weights = toList(opts.weight).filter(function (w) {
    return w !== "variable";
  });
  var italic = toList(opts.style).indexOf("italic") !== -1;
  if (weights.length) {
    var specs = [];
    [0, 1].forEach(function (ital) {
      if (ital && !italic) return;
      weights.forEach(function (w) {
        specs.push(italic ? ital + "," + w : String(w));
      });
    });
    addLink(base + ":" + (italic ? "ital,wght@" : "wght@") + specs.join(";") + "&display=swap");
    return;
  }
  // No weight given: Next.js treats the font as variable. Ask for the full axis and fall back to the
  // default weight when the family is not variable (the API answers 400 for an impossible range).
  var variableUrl = base + ":wght@100..900&display=swap";
  fetch(variableUrl)
    .then(function (res) {
      addLink(res.ok ? variableUrl : base + "&display=swap");
    })
    .catch(function () {
      addLink(base + "&display=swap");
    });
}

function makeFont(exportName, options) {
  var opts = options || {};
  var family = exportName.replace(/_/g, " ");
  var id = (exportName + (opts.variable || "")).replace(/[^A-Za-z0-9]/g, "_").toLowerCase();
  var stack = "'" + family + "', " + toList(opts.fallback || ["system-ui", "sans-serif"]).join(", ");
  if (!injected[id]) {
    injected[id] = true;
    var css = ".__font_" + id + "{font-family:" + stack + "}";
    if (opts.variable) css += ".__variable_" + id + "{" + opts.variable + ":" + stack + "}";
    addStyle(css);
    loadFamily(family, opts);
  }
  return {
    className: "__font_" + id,
    variable: opts.variable ? "__variable_" + id : "",
    style: { fontFamily: stack },
  };
}

// Every Google family is a named export in Next.js; a Proxy answers any capitalised name.
module.exports = new Proxy(
  { __esModule: true },
  {
    get: function (target, name) {
      if (name in target) return target[name];
      if (typeof name !== "string" || !/^[A-Z]/.test(name)) return undefined;
      return function (options) {
        return makeFont(name, options);
      };
    },
  },
);
