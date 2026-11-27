// Native StoreKit 2 in-app purchases bridge (ios/App/App/IAP.swift).
// Flow: native purchase -> signed jwsRepresentation -> POST /api/billing/verify
// (server is the source of truth) -> returns the new plan. No-op on web.
import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import { isNative } from "./session";
import { api } from "../api";

export interface IapProduct {
  id: string; displayName: string; description: string;
  /** Already formatted by StoreKit in the store's own currency, e.g. "12,99 €". */
  displayPrice: string;
  /** Numeric price + ISO code, for deriving the annual discount ourselves. */
  price?: number; currencyCode?: string;
  /** price / 12, formatted by StoreKit — never re-format money in JS. */
  displayPriceMonthlyEq?: string;
}
type PurchaseResult = { status: "success" | "cancelled" | "pending" | "unknown"; jws?: string };

export interface IAPPlugin {
  getProducts(opts: { productIds: string[] }): Promise<{ products: IapProduct[] }>;
  purchase(opts: { productId: string }): Promise<PurchaseResult>;
  restore(): Promise<{ jws: string[] }>;
  /** Active entitlements WITHOUT AppStore.sync() — no password prompt. */
  syncEntitlements(): Promise<{ jws: string[] }>;
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

/** The four products as the App Store prices them for THIS customer, keyed by
 *  product id. Empty on web (no StoreKit) and on any failure — the caller then
 *  falls back to its built-in figures. Prices must never be hard-coded on the
 *  paywall: a German customer seeing "$12.99" next to Apple's "12,99 €" is a
 *  3.1.2 rejection, and the dollar figures were simply wrong everywhere outside
 *  the US store. */
export async function loadProducts(): Promise<Record<string, IapProduct>> {
  if (!isNative()) return {};
  try {
    const { products } = await IAP.getProducts({ productIds: Object.values(PRODUCT_ID) });
    return Object.fromEntries(products.map((p) => [p.id, p]));
  } catch { return {}; }
}

/** Buy a plan: native purchase → server verify. Returns the new plan, or null on
 *  user-cancel/pending. Throws on a real failure. */
export async function buyPlan(plan: "ai" | "core", period: "monthly" | "yearly"): Promise<string | null> {
  const productId = PRODUCT_ID[`${plan}:${period}`];
  if (!productId) throw new Error("unknown_product");
  const res = await IAP.purchase({ productId });
  if (res.status === "cancelled" || res.status === "pending") return null;
  if (res.status !== "success" || !res.jws) throw new Error("purchase_failed");
  const verified = await api.verifyPurchase(res.jws, "purchase");
  return verified.plan;
}

let _updates: PluginListenerHandle | null = null;

/** Close the gap between "Apple took the money" and "our server granted the plan".
 *
 * Two things, both on sign-in, both silent:
 *
 * 1. Subscribe to StoreKit's `Transaction.updates` stream, which the native
 *    plugin forwards as `transactionUpdate`. These are the transactions that do
 *    NOT come back through our own `purchase()` call: a renewal, an Ask-to-Buy
 *    approval that lands hours later, a plan change made in the App Store
 *    settings, a purchase made on another device. Nothing was listening to this
 *    event before, so every one of them was dropped.
 * 2. Read current entitlements once and verify them. This catches the case the
 *    stream cannot: a purchase whose server round-trip failed (app killed,
 *    offline) and whose transaction was already finished, so StoreKit will not
 *    re-deliver it. Without this the money is gone until the user happens to
 *    find the "Restore purchases" button.
 *
 * Idempotent and safe to call on every sign-in; a no-op on web.
 */
export async function syncPurchases(onPlan?: (plan: string) => void): Promise<void> {
  if (!isNative()) return;
  const verify = (jws: string) =>
    api.verifyPurchase(jws, "sync")
      .then((r) => { if (r?.plan) onPlan?.(r.plan); })
      .catch(() => { /* not ours, or offline — the next sign-in retries */ });

  if (!_updates) {
    try {
      _updates = await IAP.addListener("transactionUpdate", (d) => { if (d?.jws) void verify(d.jws); });
    } catch { /* old build without the listener — the sweep below still runs */ }
  }
  try {
    const { jws } = await IAP.syncEntitlements();
    for (const j of jws) await verify(j);
  } catch { /* old native build without syncEntitlements */ }
}

/** Restore: sync entitlements → verify each → ask Apple for the live status.
 *
 *  The final step matters on its own. Receipts tell us what the device holds;
 *  only Apple's status endpoint tells us whether the subscription is still
 *  alive right now. If a renewal or an expiry webhook was lost, this is the one
 *  button that puts the account right without writing to support. */
export async function restorePurchases(): Promise<string | null> {
  const { jws } = await IAP.restore();
  let plan: string | null = null;
  for (const j of jws) {
    try { plan = (await api.verifyPurchase(j, "restore")).plan; } catch { /* skip non-matching */ }
  }
  try {
    const r = await api.refreshBilling();
    if (r?.checked && r.plan) plan = r.plan;
  } catch { /* reconciliation is a bonus, never the reason restore fails */ }
  return plan;
}
