// Preview shim for next/image: a plain <img>; `fill` becomes absolute positioning, no optimisation.
var React = require("react");

var NEXT_ONLY_PROPS = [
  "src",
  "fill",
  "priority",
  "loader",
  "quality",
  "placeholder",
  "blurDataURL",
  "unoptimized",
  "onLoadingComplete",
  "overrideSrc",
];

function Image(props) {
  var rest = Object.assign({}, props);
  NEXT_ONLY_PROPS.forEach(function (key) {
    delete rest[key];
  });
  var src = typeof props.src === "object" && props.src !== null ? props.src.src : props.src;
  if (props.loader) src = props.loader({ src: src, width: Number(props.width) || 1920, quality: props.quality });
  var style = props.fill
    ? Object.assign({ position: "absolute", inset: 0, width: "100%", height: "100%" }, props.style)
    : props.style;
  if (props.fill) {
    delete rest.width;
    delete rest.height;
  }
  return React.createElement(
    "img",
    Object.assign(rest, {
      src: src,
      style: style,
      loading: props.priority ? "eager" : props.loading || "lazy",
      decoding: "async",
      fetchPriority: props.priority ? "high" : undefined,
    }),
  );
}

module.exports = Image;
module.exports.default = Image;
module.exports.__esModule = true;
