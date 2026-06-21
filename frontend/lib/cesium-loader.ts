/* eslint-disable @typescript-eslint/no-explicit-any */

export type CesiumNamespace = any;

let loadPromise: Promise<CesiumNamespace> | null = null;

export function loadCesium(): Promise<CesiumNamespace> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Cesium can only load in the browser"));
  }

  const win = window as any;
  if (win.Cesium) return Promise.resolve(win.Cesium);
  if (loadPromise) return loadPromise;

  win.CESIUM_BASE_URL = "/cesium/";

  loadPromise = new Promise((resolve, reject) => {
    if (!document.querySelector('link[href="/cesium/Widgets/widgets.css"]')) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "/cesium/Widgets/widgets.css";
      document.head.appendChild(link);
    }

    const existing = document.querySelector('script[src="/cesium/Cesium.js"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(win.Cesium));
      existing.addEventListener("error", reject);
      return;
    }

    const script = document.createElement("script");
    script.src = "/cesium/Cesium.js";
    script.async = true;
    script.onload = () => {
      const token = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
      if (token && win.Cesium?.Ion) {
        win.Cesium.Ion.defaultAccessToken = token;
      }
      resolve(win.Cesium);
    };
    script.onerror = () => reject(new Error("Failed to load Cesium.js"));
    document.body.appendChild(script);
  });

  return loadPromise;
}
