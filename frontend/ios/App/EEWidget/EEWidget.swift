import SwiftUI
import WidgetKit

// Executive English lock-screen widget: rotates the phrases the user is
// currently studying. No auth and no network here — the main app drops
// {en, ru, b(atch)} JSON into the shared App-Group container (WidgetBridge.swift)
// and this TimelineProvider builds a local rotation from it.

private let appGroup = "group.net.executiveenglish.app"   // = WidgetBridgePlugin.appGroup
private let phrasesKey = "ee.widget.phrases"

struct WPhrase: Codable {
    let en: String
    let ru: String
    let b: Int          // batch id → deep link target
}

private let sample = WPhrase(en: "Let me cut to it.", ru: "сразу к делу", b: 0)

private func loadPhrases() -> [WPhrase] {
    guard let defaults = UserDefaults(suiteName: appGroup),
          let json = defaults.string(forKey: phrasesKey),
          let data = json.data(using: .utf8),
          let arr = try? JSONDecoder().decode([WPhrase].self, from: data)
    else { return [] }
    return arr.filter { !$0.en.isEmpty }
}

struct PhraseEntry: TimelineEntry {
    let date: Date
    let phrase: WPhrase
    let isPlaceholder: Bool
}

struct PhraseProvider: TimelineProvider {
    func placeholder(in context: Context) -> PhraseEntry {
        PhraseEntry(date: .now, phrase: sample, isPlaceholder: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (PhraseEntry) -> Void) {
        let p = loadPhrases().randomElement() ?? sample
        completion(PhraseEntry(date: .now, phrase: p, isPlaceholder: false))
    }

    // A shuffled pass over the study set, one phrase every 20 minutes (WidgetKit
    // treats sub-15-min steps as best-effort anyway). .atEnd → the next pass
    // reshuffles. With no data yet: show the sample and retry hourly.
    func getTimeline(in context: Context, completion: @escaping (Timeline<PhraseEntry>) -> Void) {
        let phrases = loadPhrases()
        guard !phrases.isEmpty else {
            let entry = PhraseEntry(date: .now, phrase: sample, isPlaceholder: true)
            completion(Timeline(entries: [entry], policy: .after(.now.addingTimeInterval(3600))))
            return
        }
        let step: TimeInterval = 20 * 60
        let start = Date()
        let entries = phrases.shuffled().prefix(24).enumerated().map { i, p in
            PhraseEntry(date: start.addingTimeInterval(Double(i) * step),
                        phrase: p, isPlaceholder: false)
        }
        completion(Timeline(entries: Array(entries), policy: .atEnd))
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
            VStack(alignment: .leading, spacing: 1) {
                Text(entry.phrase.en)
                    .font(.system(size: 14, weight: .semibold))
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                if !entry.phrase.ru.isEmpty {
                    Text(entry.phrase.ru)
                        .font(.system(size: 11))
                        .opacity(0.75)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .widgetURL(deepLink)
            .widgetChrome(nil)
        default: // .systemSmall on the home screen — brand card
            VStack(alignment: .leading, spacing: 6) {
                Text("EXECUTIVE ENGLISH")
                    .font(.system(size: 8, weight: .bold))
                    .kerning(0.8)
                    .opacity(0.7)
                Spacer(minLength: 0)
                Text(entry.phrase.en)
                    .font(.system(size: 15, weight: .semibold))
                    .lineLimit(4)
                    .minimumScaleFactor(0.65)
                if !entry.phrase.ru.isEmpty {
                    Text(entry.phrase.ru)
                        .font(.system(size: 11))
                        .opacity(0.75)
                        .lineLimit(2)
                }
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
