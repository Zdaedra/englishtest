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
  // --- 7 presence-направлений (новый ядровый продукт) ---
  {
    slug: "charisma",
    en: "Charisma & Magnetism",
    ru: "Харизма",
    blurb: "Войти в комнату, держать стол, быть тем, к кому тянет.",
    order: 1,
  },
  {
    slug: "flirt",
    en: "Flirt & Attraction",
    ru: "Флирт и притяжение",
    blurb: "Магнетизм из уверенности: сигнал, игра, накал.",
    order: 2,
  },
  {
    slug: "intimacy",
    en: "Intimacy & Bonds",
    ru: "Близость и узы",
    blurb: "Presence под эмоциональной нагрузкой: близость, ремонт, границы.",
    order: 3,
  },
  {
    slug: "lead-presence",
    en: "Leadership Without Title",
    ru: "Лидерство без должности",
    blurb: "Вести без полномочий: взять комнату, ответственность, спокойствие.",
    order: 4,
  },
  {
    slug: "composure",
    en: "Composure & Dignity",
    ru: "Самообладание и достоинство",
    blurb: "Не клюнуть на провокацию, держать лицо, остаться собой.",
    order: 5,
  },
  {
    slug: "gravitas",
    en: "Gravitas in Crisis",
    ru: "Гравитас в кризисе",
    blurb: "Вес и команда на максимальном давлении: war-room, ЧП, hot seat.",
    order: 6,
  },
  {
    slug: "stage",
    en: "Stage & Spotlight",
    ru: "Сцена и публичность",
    blurb: "Быть видимым: сцена, камера, зал, пресса.",
    order: 7,
  },
  // --- 13 бизнес-эталонов (старые домены) ---
  {
    slug: "live-tone",
    en: "Live Tone & Disagreement",
    ru: "Живой тон и несогласие",
    blurb: "Несогласие, мягкая прямота и живая реакция в моменте.",
    order: 8,
  },
  {
    slug: "pitch",
    en: "Pitch & Persuasion",
    ru: "Питч и убеждение",
    blurb: "Захватить внимание и продать идею за минуту.",
    order: 9,
  },
  {
    slug: "negotiation",
    en: "Negotiation",
    ru: "Переговоры",
    blurb: "Условия, уступки, давление и закрытие сделки.",
    order: 10,
  },
  {
    slug: "pressure",
    en: "Under Pressure: Q&A",
    ru: "Под давлением",
    blurb: "Острые вопросы, защита позиции, мысли вслух.",
    order: 11,
  },
  {
    slug: "repair",
    en: "Apology & Repair",
    ru: "Извинения и repair",
    blurb: "Признать ошибку и восстановить доверие без потери лица.",
    order: 12,
  },
  {
    slug: "leadership",
    en: "Team & Leadership Voice",
    ru: "Голос лидера",
    blurb: "Фидбек, видение и тон, который ведёт за собой.",
    order: 13,
  },
  {
    slug: "requests",
    en: "Requests & Status",
    ru: "Просьбы и апдейты",
    blurb: "Просьбы, делегирование и статусы без воды.",
    order: 14,
  },
  {
    slug: "written",
    en: "Written Register",
    ru: "Письменный регистр",
    blurb: "Имейлы и сообщения: тон, краткость, регистр.",
    order: 15,
  },
  {
    slug: "small-talk",
    en: "Small Talk & Meetings",
    ru: "Small talk и встречи",
    blurb: "Лёгкий вход, мосты и разговор вокруг дела.",
    order: 16,
  },
];

export const SECTION_BY_SLUG: Record<string, Section> = Object.fromEntries(
  SECTIONS.map((s) => [s.slug, s])
);

export const orderedSections = (): Section[] =>
  [...SECTIONS].sort((a, b) => a.order - b.order);

// Localized section name / blurb (i18n). Falls back to the Russian field in this
// file if a key is missing. Callers must also use useI18n() so they re-render on
// language change.
import { tg } from "../i18n";
export function sectionName(slug: string): string {
  const k = `section.${slug}.name`;
  const v = tg(k);
  return v === k ? (SECTION_BY_SLUG[slug]?.ru || slug) : v;
}
export function sectionBlurb(slug: string): string {
  const k = `section.${slug}.blurb`;
  const v = tg(k);
  return v === k ? (SECTION_BY_SLUG[slug]?.blurb || "") : v;
}
