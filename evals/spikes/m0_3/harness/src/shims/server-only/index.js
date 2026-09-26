// Preview shim: a module that imports server-only cannot run in the browser (preview contract).
throw new Error("[preview contract] 'server-only' was imported; the preview runs frontend code only.");
