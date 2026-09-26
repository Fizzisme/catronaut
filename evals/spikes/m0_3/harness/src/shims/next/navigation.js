// Preview shim for next/navigation (App Router hooks).
var React = require("react");
var router = require("./dist/catronaut/router");

function useLocation() {
  return React.useSyncExternalStore(router.subscribe, router.getSnapshot);
}

function useRouter() {
  return React.useMemo(function () {
    return {
      push: function (href, options) {
        router.navigate(href, options);
      },
      replace: function (href, options) {
        router.navigate(href, Object.assign({}, options, { replace: true }));
      },
      back: function () {
        window.history.back();
      },
      forward: function () {
        window.history.forward();
      },
      refresh: router.refresh,
      prefetch: function () {},
    };
  }, []);
}

function usePathname() {
  return useLocation().split("?")[0];
}

function useSearchParams() {
  var location = useLocation();
  return React.useMemo(
    function () {
      return new URLSearchParams(location.split("?")[1] || "");
    },
    [location],
  );
}

function useParams() {
  return React.useContext(router.ParamsContext);
}

function useSelectedLayoutSegments() {
  return usePathname().split("/").filter(Boolean);
}

function useSelectedLayoutSegment() {
  var segments = useSelectedLayoutSegments();
  return segments.length ? segments[0] : null;
}

function controlFlow(digest) {
  var error = new Error(digest);
  error.digest = digest;
  return error;
}

function notFound() {
  throw controlFlow("NEXT_NOT_FOUND");
}

function redirect(href) {
  throw controlFlow("NEXT_REDIRECT;" + href);
}

module.exports = {
  __esModule: true,
  useRouter: useRouter,
  usePathname: usePathname,
  useSearchParams: useSearchParams,
  useParams: useParams,
  useSelectedLayoutSegment: useSelectedLayoutSegment,
  useSelectedLayoutSegments: useSelectedLayoutSegments,
  notFound: notFound,
  redirect: redirect,
  permanentRedirect: redirect,
};
