import SwiftUI
import WidgetKit

// Executive English lock-screen widget: rotates the phrases the user is
// currently studying. No auth and no network here — the main app drops
// {en, b(atch), d(ue)} JSON into the shared App-Group container (WidgetBridge.swift)
// and this TimelineProvider builds a local rotation from it. We render the full
// phrase and nothing else — no gloss/keyword line.

private let appGroup = "group.net.executiveenglish.app"   // = WidgetBridgePlugin.appGroup
private let phrasesKey = "ee.widget.phrases"
private let dueKey = "ee.widget.due"                       // = WidgetBridgePlugin.dueKey

struct WPhrase: Codable {
    let en: String
    let b: Int          // batch id → deep link target
    let d: Int?         // 1 = this phrase is due (slipping) — leads the rotation
}

private let sample = WPhrase(en: "Let me cut to it.", b: 0, d: 0)

private func loadPhrases() -> [WPhrase] {
    guard let defaults = UserDefaults(suiteName: appGroup),
          let json = defaults.string(forKey: phrasesKey),
          let data = json.data(using: .utf8),
          let arr = try? JSONDecoder().decode([WPhrase].self, from: data)
    else { return [] }
    return arr.filter { !$0.en.isEmpty }
}

private func loadDueCount() -> Int {
    UserDefaults(suiteName: appGroup)?.integer(forKey: dueKey) ?? 0
}

// Deterministic "phrase of the day": DUE phrases first, then the rest, indexed
// by the calendar day (+offset). Every timeline rebuild during a day lands on the
// same phrase — one phrase, all day — and it advances at local midnight.
private func phraseForDay(_ phrases: [WPhrase], offset: Int = 0) -> WPhrase? {
    let ordered = phrases.filter { ($0.d ?? 0) == 1 } + phrases.filter { ($0.d ?? 0) != 1 }
    guard !ordered.isEmpty else { return nil }
    let cal = Calendar.current
    let day = cal.ordinality(of: .day, in: .era, for: cal.startOfDay(for: Date())) ?? 0
    let n = ordered.count
    return ordered[((day + offset) % n + n) % n]
}

struct PhraseEntry: TimelineEntry {
    let date: Date
    let phrase: WPhrase
    let dueCount: Int
    let isPlaceholder: Bool
}

struct PhraseProvider: TimelineProvider {
    func placeholder(in context: Context) -> PhraseEntry {
        PhraseEntry(date: .now, phrase: sample, dueCount: 0, isPlaceholder: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (PhraseEntry) -> Void) {
        let p = phraseForDay(loadPhrases()) ?? sample
        completion(PhraseEntry(date: .now, phrase: p, dueCount: loadDueCount(), isPlaceholder: false))
    }

    // ONE phrase per day. The pick is deterministic from the calendar day, so it
    // holds all day (every rebuild lands on the same phrase) and flips at local
    // midnight. DUE phrases (slipping) sit at the front, so they come up on the
    // soonest days. We lay out 14 days ahead; .atEnd reloads after that (and the
    // app re-pushes on foreground). No data yet: show the sample and retry hourly.
    func getTimeline(in context: Context, completion: @escaping (Timeline<PhraseEntry>) -> Void) {
        let phrases = loadPhrases()
        let due = loadDueCount()
        guard !phrases.isEmpty else {
            let entry = PhraseEntry(date: .now, phrase: sample, dueCount: 0, isPlaceholder: true)
            completion(Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(3600))))
            return
        }
        let cal = Calendar.current
        let startOfToday = cal.startOfDay(for: Date())
        let entries = (0..<14).map { d -> PhraseEntry in
            let date = cal.date(byAdding: .day, value: d, to: startOfToday) ?? startOfToday
            let phrase = phraseForDay(phrases, offset: d) ?? sample
            return PhraseEntry(date: date, phrase: phrase, dueCount: due, isPlaceholder: false)
        }
        completion(Timeline(entries: entries, policy: .atEnd))
    }
}

// iOS 17 wants containerBackground; iOS 16 renders fine without it.
private extension View {
    @ViewBuilder func widgetChrome(_ fill: Color?) -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            containerBackground(for: .widget) { fill ?? Color.clear }
        } else if let fill {
            ZStack { fill; self }
        } else {
            self
        }
    }
}

private let brandGreen = Color(red: 0x1C / 255.0, green: 0x8C / 255.0, blue: 0x63 / 255.0)

struct EEWidgetView: View {
    @Environment(\.widgetFamily) var family
    let entry: PhraseEntry

    private var deepLink: URL? {
        URL(string: entry.phrase.b > 0
            ? "executiveenglish://batch/\(entry.phrase.b)"
            : "executiveenglish://battle")
    }

    var body: some View {
        switch family {
        case .accessoryInline:
            // One line on the clock row — the phrase only.
            Text(entry.phrase.en)
                .widgetURL(deepLink)
                .widgetChrome(nil)
        case .accessoryRectangular:
            // The whole phrase, as large as the row allows — nothing else.
            Text(entry.phrase.en)
                .font(.system(size: 15, weight: .semibold))
                .lineLimit(3)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .widgetURL(deepLink)
                .widgetChrome(nil)
        default: // .systemSmall on the home screen — brand card
            VStack(alignment: .leading, spacing: 6) {
                // The eyebrow becomes the SRS nudge when something is slipping:
                // "N К ОСВЕЖЕНИЮ" instead of the brand line.
                Text(entry.dueCount > 0 ? "\(entry.dueCount) К ОСВЕЖЕНИЮ" : "EXECUTIVE ENGLISH")
                    .font(.system(size: 8, weight: .bold))
                    .kerning(0.8)
                    .opacity(entry.dueCount > 0 ? 0.95 : 0.7)
                // The whole phrase, big — nothing else on the card.
                Text(entry.phrase.en)
                    .font(.system(size: 18, weight: .semibold))
                    .lineLimit(5)
                    .minimumScaleFactor(0.6)
                Spacer(minLength: 0)
            }
            .foregroundColor(.white)
            .padding(14)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            .widgetURL(deepLink)
            .widgetChrome(brandGreen)
        }
    }
}

@main
struct EEWidgetBundle: WidgetBundle {
    var body: some Widget { EEWidget() }
}

struct EEWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "EEPhraseWidget", provider: PhraseProvider()) { entry in
            EEWidgetView(entry: entry)
        }
        .configurationDisplayName("Фраза в работе")
        .description("Ротация фраз, которые ты сейчас учишь.")
        .supportedFamilies([.accessoryRectangular, .accessoryInline, .systemSmall])
    }
}
