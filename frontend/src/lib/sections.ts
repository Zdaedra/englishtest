// The library's top-level skill domains ("Разделы"). A consilium of Opus + GPT
// distilled these 9 situation-based sections for a non-native founder; each holds
// one or more pattern batches. Metadata is static (no API): the backend only tags
// each batch with a `section` slug, the names/blurbs/order live here.

export type Section = {
  slug: string;
  en: string;
  ru: string;
  blurb: string;
  order: number;
};

export const SECTIONS: Section[] = [
  {
    slug: "live-tone",
    en: "Live Tone & Disagreement",
    ru: "Живой тон и несогласие",
    blurb: "Несогласие, мягкая прямота и живая реакция в моменте.",
    order: 1,
  },
  {
    slug: "pitch",
    en: "Pitch & Persuasion",
    ru: "Питч и убеждение",
    blurb: "Захватить внимание и продать идею за минуту.",
    order: 2,
  },
  {
    slug: "negotiation",
    en: "Negotiation",
    ru: "Переговоры",
    blurb: "Условия, уступки, давление и закрытие сделки.",
    order: 3,
  },
  {
    slug: "pressure",
    en: "Under Pressure: Q&A",
    ru: "Под давлением",
    blurb: "Острые вопросы, защита позиции, мысли вслух.",
    order: 4,
  },
  {
    slug: "repair",
    en: "Apology & Repair",
    ru: "Извинения и repair",
    blurb: "Признать ошибку и восстановить доверие без потери лица.",
    order: 5,
  },
  {
    slug: "leadership",
    en: "Team & Leadership Voice",
    ru: "Голос лидера",
    blurb: "Фидбек, видение и тон, который ведёт за собой.",
    order: 6,
  },
  {
    slug: "requests",
    en: "Requests & Status",
    ru: "Просьбы и апдейты",
    blurb: "Просьбы, делегирование и статусы без воды.",
    order: 7,
  },
  {
    slug: "written",
    en: "Written Register",
    ru: "Письменный регистр",
    blurb: "Имейлы и сообщения: тон, краткость, регистр.",
    order: 8,
  },
  {
    slug: "small-talk",
    en: "Small Talk & Meetings",
    ru: "Small talk и встречи",
    blurb: "Лёгкий вход, мосты и разговор вокруг дела.",
    order: 9,
  },
];

export const SECTION_BY_SLUG: Record<string, Section> = Object.fromEntries(
  SECTIONS.map((s) => [s.slug, s])
);

export const orderedSections = (): Section[] =>
  [...SECTIONS].sort((a, b) => a.order - b.order);
