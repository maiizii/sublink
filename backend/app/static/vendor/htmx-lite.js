(function () {
  if (typeof window === "undefined") {
    return;
  }

  if (window.htmx && window.htmx.__SUBLINK_USE_FALLBACK__ !== true) {
    return;
  }

  function toArray(value) {
    if (Array.isArray(value)) {
      return value.slice();
    }
    return [value];
  }

  function dispatch(target, eventName, detail) {
    if (!(target instanceof EventTarget) || !eventName) {
      return;
    }
    const event = new CustomEvent(eventName, {
      bubbles: true,
      cancelable: true,
      detail: detail || null,
    });
    target.dispatchEvent(event);
  }

  function onLoad(callback) {
    if (typeof callback !== "function") {
      return;
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  function trigger(target, eventName, detail) {
    if (!eventName) {
      return;
    }
    const targets = target ? toArray(target) : [document.body];
    targets.forEach((item) => {
      if (item instanceof EventTarget) {
        dispatch(item, eventName, detail);
      }
    });
  }

  window.htmx = {
    version: "lite-0.1",
    config: {
      useFallback: true,
    },
    __SUBLINK_USE_FALLBACK__: true,
    trigger,
    onLoad,
    off: function () {},
    on: function () {},
    process: function () {},
  };
})();
