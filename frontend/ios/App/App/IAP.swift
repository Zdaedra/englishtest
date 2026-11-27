import Foundation
import StoreKit
import Capacitor

// Native StoreKit 2 in-app purchases. The JS layer asks for products, starts a
// purchase, or restores; we hand back the signed `jwsRepresentation` of each
// transaction, which the backend (/api/billing/verify) verifies against Apple's
// root CAs. No third-party SDK — StoreKit 2 + our own server (locked decision).
//
// Registered in MainViewController.capacitorDidLoad() (NavBar.swift) like NavBar.
@objc(IAPPlugin)
public class IAPPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "IAPPlugin"
    public let jsName = "IAP"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getProducts", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "purchase", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "restore", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "syncEntitlements", returnType: CAPPluginReturnPromise),
    ]

    private var updatesTask: Task<Void, Never>?

    // Transactions can arrive outside an explicit purchase (renewals, Ask-to-Buy
    // approval, a purchase made on another device). Stream them to JS so the
    // backend stays in sync; the server is still the source of truth.
    override public func load() {
        updatesTask = Task.detached { [weak self] in
            for await update in Transaction.updates {
                guard let self = self else { continue }
                self.notifyListeners("transactionUpdate", data: ["jws": update.jwsRepresentation])
                if case .verified(let tx) = update { await tx.finish() }
            }
        }
    }

    deinit { updatesTask?.cancel() }

    @objc func getProducts(_ call: CAPPluginCall) {
        guard let ids = call.getArray("productIds", String.self), !ids.isEmpty else {
            call.reject("productIds required"); return
        }
        Task {
            do {
                let products = try await Product.products(for: ids)
                let out: [[String: Any]] = products.map { p in
                    [
                        "id": p.id,
                        "displayName": p.displayName,
                        "description": p.description,
                        "displayPrice": p.displayPrice,
                        // Numeric price + currency so JS can derive the
                        // per-month equivalent and the annual discount in the
                        // customer's own currency. displayPrice alone is a
                        // formatted string and cannot be divided.
                        "price": NSDecimalNumber(decimal: p.price).doubleValue,
                        "currencyCode": p.priceFormatStyle.currencyCode,
                        // The per-month equivalent of a yearly plan, formatted by
                        // StoreKit itself. Formatting it on the JS side instead
                        // produces a DIFFERENT look for the same currency — the
                        // AlefSwitch release hit exactly this: "599.00 RUB" next
                        // to "49,92 RUB" on one screen. Both prices on the card
                        // must come out of the same formatter. Meaningless for
                        // monthly products; the paywall only reads it on yearly.
                        "displayPriceMonthlyEq": (p.price / 12).formatted(p.priceFormatStyle),
                    ]
                }
                call.resolve(["products": out])
            } catch {
                call.reject("products_failed", nil, error)
            }
        }
    }

    @objc func purchase(_ call: CAPPluginCall) {
        guard let id = call.getString("productId") else { call.reject("productId required"); return }
        Task {
            do {
                guard let product = try await Product.products(for: [id]).first else {
                    call.reject("product_not_found"); return
                }
                let result = try await product.purchase()
                switch result {
                case .success(let verification):
                    // Hand the signed JWS to JS regardless of local verify — the
                    // backend does the authoritative signature check.
                    if case .verified(let tx) = verification { await tx.finish() }
                    call.resolve(["status": "success", "jws": verification.jwsRepresentation])
                case .userCancelled:
                    call.resolve(["status": "cancelled"])
                case .pending:
                    call.resolve(["status": "pending"])
                @unknown default:
                    call.resolve(["status": "unknown"])
                }
            } catch {
                call.reject("purchase_failed", nil, error)
            }
        }
    }

    // Silent entitlement read: what StoreKit currently considers active, WITHOUT
    // AppStore.sync(), which prompts for the App Store password. Called on every
    // sign-in so a purchase whose server round-trip never happened (app killed
    // mid-purchase, offline, Ask-to-Buy approved hours later) is picked up with no
    // user action. The visible "Restore purchases" button still calls restore()
    // below, which does sync and may prompt — that one is user-initiated.
    @objc func syncEntitlements(_ call: CAPPluginCall) {
        Task {
            var jws: [String] = []
            for await entitlement in Transaction.currentEntitlements {
                jws.append(entitlement.jwsRepresentation)
            }
            call.resolve(["jws": jws])
        }
    }

    @objc func restore(_ call: CAPPluginCall) {
        Task {
            try? await AppStore.sync()
            var jws: [String] = []
            for await entitlement in Transaction.currentEntitlements {
                jws.append(entitlement.jwsRepresentation)
            }
            call.resolve(["jws": jws])
        }
    }
}
