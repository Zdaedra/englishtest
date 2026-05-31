import React from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import Library from "./pages/Library";
import Learning from "./pages/Learning";
import Onboarding from "./pages/Onboarding";
import BatchHome from "./pages/BatchHome";
import Lesson1 from "./pages/Lesson1";
import Lesson2 from "./pages/Lesson2";
import Lesson3 from "./pages/Lesson3";
import Playback from "./pages/Playback";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";
import ImportBatch from "./pages/ImportBatch";
import "./index.css";

const router = createHashRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Library /> },
      { path: "learn", element: <Learning /> },
      { path: "batch/:id", element: <BatchHome /> },
      { path: "batch/:id/lesson/1", element: <Lesson1 /> },
      { path: "batch/:id/lesson/2", element: <Lesson2 /> },
      { path: "batch/:id/lesson/3", element: <Lesson3 /> },
      { path: "play", element: <Playback /> },
      { path: "profile", element: <Profile /> },
      { path: "settings", element: <Settings /> },
      { path: "import", element: <ImportBatch /> },
    ],
  },
  { path: "/onboarding", element: <Onboarding /> },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);

// A service worker only runs in a secure context (HTTPS / localhost). Over plain
// HTTP (the IP deploy) registration is blocked anyway, so there we instead tear
// down any previously-stuck SW + caches — that's the #1 cause of a stale shell
// surviving a deploy. On HTTPS we register normally.
if ("serviceWorker" in navigator) {
  if (window.isSecureContext) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  } else {
    navigator.serviceWorker
      .getRegistrations()
      .then((rs) => rs.forEach((r) => r.unregister()))
      .catch(() => {});
    if ("caches" in window) {
      caches.keys().then((ks) => ks.forEach((k) => caches.delete(k))).catch(() => {});
    }
  }
}
