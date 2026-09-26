// Preview shim for next/dynamic: React.lazy + Suspense; `ssr` is meaningless in the browser.
var React = require("react");

function dynamic(loader, options) {
  var opts = options || {};
  var Lazy = React.lazy(function () {
    return loader().then(function (mod) {
      return { default: mod && mod.default ? mod.default : mod };
    });
  });
  function Dynamic(props) {
    var fallback = opts.loading ? React.createElement(opts.loading, { isLoading: true }) : null;
    return React.createElement(React.Suspense, { fallback: fallback }, React.createElement(Lazy, props));
  }
  return Dynamic;
}

module.exports = dynamic;
module.exports.default = dynamic;
module.exports.__esModule = true;
