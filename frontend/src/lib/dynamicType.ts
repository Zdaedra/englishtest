// Dynamic Type (HIG): scale the whole UI with the iOS system text-size setting.
//
// All CSS font-sizes are expressed in `rem`, so they resolve against the root
// (<html>) font-size. By default that is 16px — which is exactly our design base,
// so the web app and the iOS app at default text size render byte-identical.
//
// On iOS, WKWebView maps the CSS keyword `-apple-system-body` to the active
// Content Size Category, so a hidden probe element reveals the user's preferred
// body size. We normalize it against the default (17px → "Large"), clamp it so
// layouts never explode or collapse, and set the root font-size accordingly.
//
// Gated to iOS native only: Android WebView does not honour `-apple-system-body`,
// and desktop browsers have their own conventions — both keep the 16px base.
import { Capacitor } from "@capacitor/core";

const DESIGN_BASE = 16;     // our CSS rem base (px)
const SYSTEM_DEFAULT = 17;  // -apple-system-body at the default ("Large") setting
const MIN_SCALE = 0.9;      // don't shrink below ~14.4px base
const MAX_SCALE = 1.45;     // cap growth so tight layouts survive AX sizes

function isIOS(): boolean {
  try { return Capacitor.getPlatform() === "ios"; } catch { return false; }
}

function measureSystemBody(): number {
  const probe = document.createElement("span");
  probe.style.cssText =
    "position:absolute;top:-9999px;left:-9999px;visibility:hidden;" +
    "pointer-events:none;font:-apple-system-body;";
  probe.textContent = "X";
  document.body.appendChild(probe);
  const px = parseFloat(getComputedStyle(probe).fontSize) || SYSTEM_DEFAULT;
  probe.remove();
  return px;
}

function apply(): void {
  const sys = measureSystemBody();
  let scale = sys / SYSTEM_DEFAULT;
  if (!isFinite(scale) || scale <= 0) scale = 1;
  scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale));
  document.documentElement.style.fontSize = `${(DESIGN_BASE * scale).toFixed(2)}px`;
}

export function initDynamicType(): void {
  if (typeof document === "undefined" || !isIOS()) return;
  const run = () => { try { apply(); } catch { /* non-fatal; keep 16px base */ } };
  if (document.body) run();
  else document.addEventListener("DOMContentLoaded", run, { once: true });
  // A Dynamic Type change happens in Settings, then the app returns to foreground.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") run();
  });
  window.addEventListener("focus", run);
}
