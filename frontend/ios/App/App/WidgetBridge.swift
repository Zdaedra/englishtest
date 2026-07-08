import Capacitor
import Foundation
import WidgetKit

// Bridge from the JS app to the lock-screen widget (EEWidget extension).
// The app is the only side with auth: it periodically drops the user's current
// study phrases as JSON into the shared App-Group container; the widget's
// TimelineProvider reads them and rotates with zero network access.
// Registered in MainViewController.capacitorDidLoad() (NavBar.swift) like NavBar.
@objc(WidgetBridgePlugin)
public class WidgetBridgePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "WidgetBridgePlugin"
    public let jsName = "WidgetBridge"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "update", returnType: CAPPluginReturnPromise)
    ]

    // Must match EEWidget/EEWidget.swift and both .entitlements files.
    static let appGroup = "group.net.executiveenglish.app"
    static let phrasesKey = "ee.widget.phrases"
    static let updatedKey = "ee.widget.updated"

    // update({ phrases: [{en, ru, b}] }) — replaces the widget's phrase set and
    // asks WidgetKit to rebuild timelines. Empty array clears it (logout).
    @objc func update(_ call: CAPPluginCall) {
        guard let phrases = call.getArray("phrases") else {
            call.reject("phrases required")
            return
        }
        guard let defaults = UserDefaults(suiteName: Self.appGroup) else {
            call.reject("app group unavailable")
            return
        }
        guard JSONSerialization.isValidJSONObject(phrases),
              let data = try? JSONSerialization.data(withJSONObject: phrases),
              let json = String(data: data, encoding: .utf8) else {
            call.reject("phrases not serializable")
            return
        }
        defaults.set(json, forKey: Self.phrasesKey)
        defaults.set(Date().timeIntervalSince1970, forKey: Self.updatedKey)
        WidgetCenter.shared.reloadAllTimelines()
        call.resolve(["count": phrases.count])
    }
}
