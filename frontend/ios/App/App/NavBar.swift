import Foundation
import UIKit
import Capacitor

// Native bottom navigation — a thin Liquid-Glass layer drawn OVER the WKWebView.
// react-router still owns navigation: this bar is a dumb renderer + event source.
// iOS 26 → real UIGlassEffect (refraction, interactive press). iOS 16–25 → frosted
// UIBlurEffect fallback. The web bar (.nav-dock) is hidden when this is presented.

// MARK: - The bar view

final class NavBarView: UIView {
    var onSelect: ((Int) -> Void)?
    var onSearch: (() -> Void)?

    private let capsule = UIVisualEffectView()
    private let pill = UIVisualEffectView()          // the «глазок» — glass selection cell
    private let searchIsland = UIVisualEffectView()
    private var tabButtons: [UIControl] = []
    private var iconViews: [UIImageView] = []
    private var labelViews: [UILabel] = []
    private var sfNames: [String] = []
    private var active = 0
    private var minimized = false

    private let barHeight: CGFloat = 56
    private let searchSize: CGFloat = 56
    private let sideInset: CGFloat = 21
    private let gap: CGFloat = 8
    private let pillInset: CGFloat = 5

    private let emerald = UIColor(red: 28/255, green: 140/255, blue: 99/255, alpha: 1)
    private let selFeedback = UISelectionFeedbackGenerator()
    private let impactFeedback = UIImpactFeedbackGenerator(style: .soft)

    init(labels: [String], sf: [String]) {
        self.sfNames = sf
        super.init(frame: .zero)
        buildMaterials()
        buildTabs(labels: labels, sf: sf)
        buildSearch()
        let pan = UIPanGestureRecognizer(target: self, action: #selector(onPan(_:)))
        capsule.contentView.addGestureRecognizer(pan)
        selFeedback.prepare()
    }
    required init?(coder: NSCoder) { fatalError() }

    // MARK: build

    private func glassEffect(interactive: Bool, tint: UIColor?) -> UIVisualEffect {
        if #available(iOS 26.0, *) {
            let e = UIGlassEffect(style: .regular)
            e.isInteractive = interactive
            if let tint = tint { e.tintColor = tint }
            return e
        } else {
            return UIBlurEffect(style: .systemUltraThinMaterial)
        }
    }

    private func roundCorners(_ v: UIVisualEffectView, radius: CGFloat) {
        v.clipsToBounds = true
        v.layer.cornerRadius = radius
        v.layer.cornerCurve = .continuous
    }

    private func buildMaterials() {
        capsule.effect = glassEffect(interactive: true, tint: nil)
        roundCorners(capsule, radius: barHeight / 2)
        addSubview(capsule)

        pill.effect = glassEffect(interactive: false, tint: emerald.withAlphaComponent(0.18))
        roundCorners(pill, radius: (barHeight - pillInset * 2) / 2)
        capsule.contentView.addSubview(pill)

        searchIsland.effect = glassEffect(interactive: true, tint: nil)
        roundCorners(searchIsland, radius: searchSize / 2)
        addSubview(searchIsland)
    }

    private func buildTabs(labels: [String], sf: [String]) {
        for (i, label) in labels.enumerated() {
            let btn = UIControl()
            btn.tag = i
            btn.addTarget(self, action: #selector(onTap(_:)), for: .touchUpInside)
            btn.addTarget(self, action: #selector(onPress(_:)), for: .touchDown)
            btn.addTarget(self, action: #selector(onRelease(_:)),
                          for: [.touchUpInside, .touchUpOutside, .touchCancel])

            let icon = UIImageView()
            icon.contentMode = .center
            icon.preferredSymbolConfiguration = UIImage.SymbolConfiguration(pointSize: 19, weight: .regular)
            icon.image = UIImage(systemName: i < sf.count ? sf[i] : "circle")
            icon.isUserInteractionEnabled = false

            let lbl = UILabel()
            lbl.text = label
            lbl.font = .systemFont(ofSize: 10, weight: .semibold)
            lbl.textAlignment = .center
            lbl.isUserInteractionEnabled = false

            btn.addSubview(icon); btn.addSubview(lbl)
            capsule.contentView.addSubview(btn)
            tabButtons.append(btn); iconViews.append(icon); labelViews.append(lbl)
        }
        applyActiveStyle(animated: false)
    }

    private func buildSearch() {
        let btn = UIControl()
        btn.addTarget(self, action: #selector(onSearchTap), for: .touchUpInside)
        let icon = UIImageView()
        icon.contentMode = .center
        icon.preferredSymbolConfiguration = UIImage.SymbolConfiguration(pointSize: 21, weight: .regular)
        icon.image = UIImage(systemName: "magnifyingglass")
        icon.tintColor = .label
        icon.isUserInteractionEnabled = false
        btn.addSubview(icon)
        searchIsland.contentView.addSubview(btn)
        searchIsland.contentView.tag = 999
        objc_setAssociatedObject(searchIsland, &Self.searchBtnKey, btn, .OBJC_ASSOCIATION_RETAIN)
    }
    private static var searchBtnKey = 0

    // MARK: layout

    override func layoutSubviews() {
        super.layoutSubviews()
        // Minimized (iOS 26 scroll-edge): capsule collapses to a circular pill
        // showing only the active icon; search island fades out.
        if minimized {
            let s = barHeight
            capsule.frame = CGRect(x: 0, y: bounds.height - s, width: s, height: s)
            searchIsland.frame = CGRect(x: 0, y: bounds.height - searchSize, width: searchSize, height: searchSize)
            for (i, btn) in tabButtons.enumerated() {
                btn.frame = CGRect(x: 0, y: 0, width: s, height: s)
                iconViews[i].frame = CGRect(x: (s - 24) / 2, y: (s - 24) / 2, width: 24, height: 24)
                labelViews[i].frame = .zero
            }
            pill.frame = CGRect(x: pillInset, y: pillInset, width: s - pillInset * 2, height: s - pillInset * 2)
            return
        }
        let capW = bounds.width - searchSize - gap
        capsule.frame = CGRect(x: 0, y: bounds.height - barHeight, width: capW, height: barHeight)
        searchIsland.frame = CGRect(x: capW + gap, y: bounds.height - searchSize, width: searchSize, height: searchSize)
        if let sBtn = objc_getAssociatedObject(searchIsland, &Self.searchBtnKey) as? UIControl {
            sBtn.frame = searchIsland.contentView.bounds
            sBtn.subviews.first?.frame = sBtn.bounds
        }
        let n = max(tabButtons.count, 1)
        let colW = capsule.bounds.width / CGFloat(n)
        for (i, btn) in tabButtons.enumerated() {
            btn.frame = CGRect(x: CGFloat(i) * colW, y: 0, width: colW, height: barHeight)
            iconViews[i].frame = CGRect(x: 0, y: 8, width: colW, height: 24)
            labelViews[i].frame = CGRect(x: 0, y: 33, width: colW, height: 14)
        }
        pill.frame = pillFrame(for: active)
    }

    private func pillFrame(for index: Int) -> CGRect {
        let n = max(tabButtons.count, 1)
        let colW = capsule.bounds.width / CGFloat(n)
        return CGRect(x: CGFloat(index) * colW + pillInset, y: pillInset,
                      width: colW - pillInset * 2, height: barHeight - pillInset * 2)
    }

    // MARK: interaction

    // Press-state: sub-100ms touch-reactive dip (the "last 15%" native feel).
    @objc private func onPress(_ sender: UIControl) { scaleIcon(sender.tag, 0.88) }
    @objc private func onRelease(_ sender: UIControl) {
        scaleIcon(sender.tag, sender.tag == active ? 1.12 : 1.0)
    }
    private func scaleIcon(_ i: Int, _ s: CGFloat) {
        guard i >= 0, i < iconViews.count else { return }
        UIView.animate(withDuration: 0.12, delay: 0, options: [.allowUserInteraction, .beginFromCurrentState]) {
            self.iconViews[i].transform = CGAffineTransform(scaleX: s, y: s)
        }
    }

    // Scroll-edge minimize (driven by the plugin's scrollView KVO).
    func setMinimized(_ on: Bool) {
        guard on != minimized else { return }
        minimized = on
        UIView.animate(withDuration: 0.3, delay: 0, usingSpringWithDamping: 0.9,
                       initialSpringVelocity: 0.3, options: [.allowUserInteraction]) {
            self.setNeedsLayout(); self.layoutIfNeeded()
            self.searchIsland.alpha = on ? 0 : 1
            for (i, lbl) in self.labelViews.enumerated() {
                lbl.alpha = on ? 0 : 1
                let hidden = on && i != self.active
                self.tabButtons[i].alpha = hidden ? 0 : 1
            }
        }
    }

    @objc private func onTap(_ sender: UIControl) {
        let idx = sender.tag
        if idx != active { selFeedback.selectionChanged() }
        setActive(idx, animated: true)
        onSelect?(idx)
    }

    @objc private func onSearchTap() {
        impactFeedback.impactOccurred()
        onSearch?()
    }

    private var dragStartActive = 0
    private var lastDragIndex = -1

    @objc private func onPan(_ g: UIPanGestureRecognizer) {
        let n = max(tabButtons.count, 1)
        let colW = capsule.bounds.width / CGFloat(n)
        let x = g.location(in: capsule.contentView).x
        let frac = min(CGFloat(n - 1), max(0, x / colW - 0.5))
        switch g.state {
        case .began:
            dragStartActive = active
            lastDragIndex = active
            selFeedback.prepare()
        case .changed:
            // The «глазок» follows the finger (continuous), with a gentle magnetic
            // bias toward the nearest slot.
            let target = round(frac)
            let pull = frac * 0.7 + target * 0.3
            var f = pillFrame(for: 0)
            f.origin.x = pull * colW + pillInset
            pill.frame = f
            let near = Int(target)
            if near != lastDragIndex {
                selFeedback.selectionChanged()   // haptic per crossed slot
                lastDragIndex = near
                styleIcons(activeIndex: near, animated: true)
            }
        case .ended, .cancelled, .failed:
            let landed = Int(round(frac))
            setActive(landed, animated: true)
            if landed != dragStartActive { onSelect?(landed) }
        default: break
        }
    }

    // MARK: state / style

    func setActive(_ index: Int, animated: Bool) {
        active = max(0, min(index, tabButtons.count - 1))
        let anim = {
            self.pill.frame = self.pillFrame(for: self.active)
            self.applyActiveStyle(animated: false)
        }
        if animated {
            UIView.animate(withDuration: 0.42, delay: 0, usingSpringWithDamping: 0.82,
                           initialSpringVelocity: 0.4, options: [.allowUserInteraction], animations: anim)
        } else { anim() }
    }

    private func applyActiveStyle(animated: Bool) { styleIcons(activeIndex: active, animated: animated) }

    private func styleIcons(activeIndex: Int, animated: Bool) {
        for (i, icon) in iconViews.enumerated() {
            let on = i == activeIndex
            let apply = {
                icon.tintColor = on ? self.emerald : .secondaryLabel
                self.labelViews[i].textColor = on ? self.emerald : .secondaryLabel
                icon.transform = on ? CGAffineTransform(scaleX: 1.12, y: 1.12) : .identity
            }
            if animated { UIView.animate(withDuration: 0.25, animations: apply) } else { apply() }
        }
    }

    func update(labels: [String]) {
        for (i, lbl) in labelViews.enumerated() where i < labels.count { lbl.text = labels[i] }
    }

    // Pin above the bottom safe area inside `host`.
    func pin(to host: UIView) {
        translatesAutoresizingMaskIntoConstraints = false
        host.addSubview(self)
        NSLayoutConstraint.activate([
            leadingAnchor.constraint(equalTo: host.leadingAnchor, constant: sideInset),
            trailingAnchor.constraint(equalTo: host.trailingAnchor, constant: -sideInset),
            bottomAnchor.constraint(equalTo: host.safeAreaLayoutGuide.bottomAnchor, constant: -6),
            heightAnchor.constraint(equalToConstant: searchSize),
        ])
    }
}

// MARK: - Capacitor plugin

// Capacitor 6 registers ONLY the plugins in capacitor.config.json's
// packageClassList (npm packages) — it does NOT auto-scan for local plugin
// classes. So a local plugin must be registered here, via the bridge VC's
// capacitorDidLoad() hook. Main.storyboard points its root VC at this class.
public class MainViewController: CAPBridgeViewController {
    public override func capacitorDidLoad() {
        bridge?.registerPluginInstance(NavBarPlugin())
        bridge?.registerPluginInstance(IAPPlugin())
    }
}

@objc(NavBarPlugin)
public class NavBarPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "NavBarPlugin"
    public let jsName = "NavBar"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "present", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setActive", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setVisible", returnType: CAPPluginReturnPromise),
    ]
    private var bar: NavBarView?
    private var scrollObs: NSKeyValueObservation?
    private var lastY: CGFloat = 0

    @objc func present(_ call: CAPPluginCall) {
        let labels = call.getArray("labels", String.self) ?? ["Library", "Learn", "Practice"]
        let sf = call.getArray("sf", String.self) ?? ["books.vertical", "waveform", "target"]
        let active = call.getInt("active") ?? 0
        DispatchQueue.main.async {
            guard let vcView = self.bridge?.viewController?.view else {
                call.reject("no host view"); return
            }
            // Mount on the window (a sibling ABOVE the WKWebView), not inside the
            // webview — otherwise web content steals the touches even though the
            // glass renders on top.
            let container = vcView.window ?? vcView.superview ?? vcView
            if self.bar == nil {
                let b = NavBarView(labels: labels, sf: sf)
                b.onSelect = { [weak self] idx in self?.notifyListeners("tabSelected", data: ["index": idx]) }
                b.onSearch = { [weak self] in self?.notifyListeners("searchTapped", data: [:]) }
                b.pin(to: container)
                self.bar = b
                // Minimize on scroll-down, expand on scroll-up (KVO on the web
                // scrollView — no per-frame bridge traffic).
                if let sv = self.webView?.scrollView {
                    self.scrollObs = sv.observe(\.contentOffset, options: [.new]) { [weak self] sv, _ in
                        guard let self = self else { return }
                        let y = sv.contentOffset.y
                        let dy = y - self.lastY
                        if abs(dy) > 6 {
                            self.bar?.setMinimized(dy > 0 && y > 40)
                            self.lastY = y
                        }
                    }
                }
            } else {
                self.bar?.update(labels: labels)
            }
            self.bar?.setActive(active, animated: false)
            self.bar?.isHidden = false
            call.resolve()
        }
    }

    @objc func setActive(_ call: CAPPluginCall) {
        let idx = call.getInt("index") ?? 0
        DispatchQueue.main.async { self.bar?.setActive(idx, animated: true); call.resolve() }
    }

    @objc func setVisible(_ call: CAPPluginCall) {
        let visible = call.getBool("visible") ?? true
        DispatchQueue.main.async { self.bar?.isHidden = !visible; call.resolve() }
    }
}
