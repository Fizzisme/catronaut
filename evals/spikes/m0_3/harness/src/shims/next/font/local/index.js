// Preview shim: local font files are binary and cannot be shipped to the preview (preview contract).
function localFont() {
  throw new Error(
    "[preview contract] next/font/local is not supported in the preview; use next/font/google instead.",
  );
}

module.exports = localFont;
module.exports.default = localFont;
module.exports.__esModule = true;
