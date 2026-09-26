// Preview shim for next/link: an <a> that navigates client-side through the preview router.
var React = require("react");
var router = require("./dist/catronaut/router");

var NEXT_ONLY_PROPS = [
  "href",
  "replace",
  "scroll",
  "prefetch",
  "shallow",
  "passHref",
  "legacyBehavior",
  "locale",
  "onNavigate",
];

function formatHref(href) {
  if (typeof href === "string") return href;
  var path = href.pathname || "";
  var query = href.query ? new URLSearchParams(href.query).toString() : "";
  return path + (query ? "?" + query : "") + (href.hash ? "#" + href.hash : "");
}

var Link = React.forwardRef(function Link(props, ref) {
  var rest = Object.assign({}, props);
  NEXT_ONLY_PROPS.forEach(function (key) {
    delete rest[key];
  });
  var href = formatHref(props.href);
  function onClick(event) {
    if (props.onClick) props.onClick(event);
    if (event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (props.target && props.target !== "_self") return;
    var url = new URL(href, window.location.href);
    if (url.origin !== window.location.origin) return;
    event.preventDefault();
    router.navigate(href, { replace: props.replace, scroll: props.scroll });
  }
  return React.createElement("a", Object.assign(rest, { ref: ref, href: href, onClick: onClick }));
});

module.exports = Link;
module.exports.default = Link;
module.exports.__esModule = true;
