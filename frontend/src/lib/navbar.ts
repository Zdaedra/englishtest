// Bridge to the native Liquid-Glass bottom bar (ios/App/App/NavBar.swift).
// No-op surface on web — callers guard with isNative(). react-router owns
// navigation; the native bar only renders + emits tab/search events.
import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";

export interface NavBarPlugin {
  present(opts: { labels: string[]; sf?: string[]; active?: number }): Promise<void>;
  setActive(opts: { index: number }): Promise<void>;
  setVisible(opts: { visible: boolean }): Promise<void>;
  addListener(event: "tabSelected", cb: (d: { index: number }) => void): Promise<PluginListenerHandle>;
  addListener(event: "searchTapped", cb: () => void): Promise<PluginListenerHandle>;
}

export const NavBar = registerPlugin<NavBarPlugin>("NavBar");

// SF Symbol per tab, index-aligned with the web TABS order (Library/Learn/Practice).
export const NAV_SF = ["books.vertical", "waveform", "target"];
