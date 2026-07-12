// Native StoreKit 2 in-app purchases bridge (ios/App/App/IAP.swift).
// Flow: native purchase -> signed jwsRepresentation -> POST /api/billing/verify
// (server is the source of truth) -> returns the new plan. No-op on web.
import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import { isNative } from "./session";
import { api } from "../api";

export interface IapProduct {
  id: string; displayName: string; description: string; displayPrice: string;
}
type PurchaseResult = { status: "success" | "cancelled" | "pending" | "unknown"; jws?: string };

export interface IAPPlugin {
  getProducts(opts: { productIds: string[] }): Promise<{ products: IapProduct[] }>;
  purchase(opts: { productId: string }): Promise<PurchaseResult>;
  restore(): Promise<{ jws: string[] }>;
  addListener(event: "transactionUpdate", cb: (d: { jws: string }) => void): Promise<PluginListenerHandle>;
}

export const IAP = registerPlugin<IAPPlugin>("IAP");

// Our plan+period → the App Store Connect product ids (must match billing.PRODUCT_PLAN).
export const PRODUCT_ID: Record<string, string> = {
  "ai:monthly": "net.executiveenglish.ai.monthly",
  "ai:yearly": "net.executiveenglish.ai.yearly",
  "core:monthly": "net.executiveenglish.core.monthly",
  "core:yearly": "net.executiveenglish.core.yearly",
};

export const iapAvailable = (): boolean => isNative();

/** Buy a plan: native purchase → server verify. Returns the new plan, or null on
 *  user-cancel/pending. Throws on a real failure. */
export async function buyPlan(plan: "ai" | "core", period: "monthly" | "yearly"): Promise<string | null> {
  const productId = PRODUCT_ID[`${plan}:${period}`];
  if (!productId) throw new Error("unknown_product");
  const res = await IAP.purchase({ productId });
  if (res.status === "cancelled" || res.status === "pending") return null;
  if (res.status !== "success" || !res.jws) throw new Error("purchase_failed");
  const verified = await api.verifyPurchase(res.jws);
  return verified.plan;
}

/** Restore: sync entitlements → verify each → return the active plan (or null). */
export async function restorePurchases(): Promise<string | null> {
  const { jws } = await IAP.restore();
  let plan: string | null = null;
  for (const j of jws) {
    try { plan = (await api.verifyPurchase(j)).plan; } catch { /* skip non-matching */ }
  }
  return plan;
}
