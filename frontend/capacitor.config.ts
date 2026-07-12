import type { CapacitorConfig } from "@capacitor/cli";

// Native iOS shell config. The web build (frontend/dist) is bundled into the app
// and loaded by WKWebView; API calls go to the remote backend (see VITE_API_BASE
// / src/api.ts). Run: `vite build` → `npx cap sync ios` → open ios/ in Xcode.
// The native project (ios/) is generated once the Apple Developer account +
// Xcode/CocoaPods are set up: `npx cap add ios`.
const config: CapacitorConfig = {
  appId: "net.executiveenglish.app", // TODO confirm bundle id in §11
  appName: "Executive English",
  webDir: "dist",
  ios: {
    contentInset: "always",
  },
};

export default config;
