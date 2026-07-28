export const ready = async (fn: () => Promise<void> | void) => {
  if (document.readyState != "loading") {
    setTimeout(async () => {
      await fn();
    }, 0);
  } else {
    document.addEventListener("DOMContentLoaded", fn);
  }
};
