export interface LearnArticle {
  slug: string;
  title: string;
  summary: string;
  readingTimeMinutes: number;
  keyTakeaways: string[];
  bodyParagraphs: string[];
  officialReferences: {
    publisher: string;
    title: string;
    url: string;
  }[];
}

export const LEARN_ARTICLES: readonly LearnArticle[] = [
  {
    slug: "pm25-vs-pm10-winter-smog",
    title: "PM2.5 vs PM10 & Why Winter Thermal Inversions Trap Urban Smog",
    summary:
      "Understand fine vs coarse particulate matter and why cool, calm winter nights concentrate pollutants near ground level.",
    readingTimeMinutes: 4,
    keyTakeaways: [
      "PM2.5 particles (<= 2.5 micrometers) penetrate deep into the lower airways and bloodstream.",
      "Winter thermal inversions form a cool surface air layer under warmer air aloft, suppressing vertical mixing.",
      "Early-morning and late-evening outdoor workouts carry higher cumulative PM2.5 exposure than midday hours.",
    ],
    bodyParagraphs: [
      "Particulate matter is categorized by aerodynamic diameter. Coarse particles (PM10) include road dust and construction debris, whereas fine particles (PM2.5) arise primarily from vehicle exhaust, solid-fuel combustion, industrial plumes, and secondary aerosol chemistry.",
      "During winter nights, ground surfaces radiate heat rapidly, chilling the lowest atmospheric layer. Calm winds and high humidity trap combustion emissions near breathing height until afternoon solar heating restores boundary-layer dispersion.",
    ],
    officialReferences: [
      {
        publisher: "World Health Organization",
        title: "Ambient (outdoor) air quality and health fact sheet",
        url: "https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health",
      },
    ],
  },
  {
    slug: "india-naqi-vs-us-epa-standards",
    title: "India NAQI vs US EPA AQI: Why Standards Must Never Be Mixed",
    summary:
      "Learn how pollutant breakpoints, averaging windows, and textual severity categories differ across national indices.",
    readingTimeMinutes: 3,
    keyTakeaways: [
      "The same PM2.5 concentration maps to different index numbers and category names under India NAQI vs US EPA AQI.",
      "India NAQI requires 24-hour averages (8-hour for CO and O3) and at least 3 valid pollutants including PM2.5 or PM10.",
      "Every AirWise badge, alert rule, and chart declares its active standard explicitly alongside non-color-only labels.",
    ],
    bodyParagraphs: [
      "Air quality indices translate multi-pollutant mass or volume concentrations into a piecewise linear sub-index scale from 0 to 500, reporting the highest pollutant sub-index as the overall AQI.",
      "Because US EPA (revised 2024 PM2.5 breakpoints) and India CPCB National AQI define distinct concentration cutoffs and category names, comparing raw AQI numbers without naming the standard leads to misleading safety conclusions.",
    ],
    officialReferences: [
      {
        publisher: "Central Pollution Control Board (India)",
        title: "National Air Quality Index Portal",
        url: "https://cpcb.nic.in/",
      },
    ],
  },
  {
    slug: "hepa-filtration-and-indoor-air-myths",
    title: "Evidence-Based Indoor Air Protection: CADR Sizing & Myths to Avoid",
    summary:
      "How to size certified HEPA purifiers to room volume, eliminate indoor smoke sources, and avoid ozone or houseplant myths.",
    readingTimeMinutes: 4,
    keyTakeaways: [
      "Without a connected indoor PM2.5 sensor, indoor air quality is unmeasured—never assume closed windows guarantee clean indoor air.",
      "Divide purifier Clean Air Delivery Rate (CADR in m³/h) by room volume (m³) to estimate Clean Air Changes per Hour (ACH).",
      "Avoid ozone-generating ionizers, and do not rely on potted houseplants to filter indoor PM2.5 smog.",
    ],
    bodyParagraphs: [
      "Source control is always step one indoors: stop incense, mosquito coils, tobacco smoke, and unvented combustion, and run an outdoor-vented kitchen exhaust hood while cooking.",
      "When outdoor smog is elevated, keep exterior windows closed and run a certified mechanical HEPA purifier sized to deliver 4–5+ clean air changes per hour in bedrooms and living spaces, paired with damp microfiber cleaning.",
    ],
    officialReferences: [
      {
        publisher: "US Environmental Protection Agency",
        title: "Guide to Air Cleaners in the Home",
        url: "https://www.epa.gov/indoor-air-quality-iaq/guide-air-cleaners-home",
      },
    ],
  },
  {
    slug: "exposure-first-commuting",
    title: "Exposure-First Commuting: Balancing Personal Health & Transport CO₂e",
    summary:
      "Why personal respiratory safety always overrides active-mobility emissions savings during severe pollution episodes.",
    readingTimeMinutes: 3,
    keyTakeaways: [
      "Walking and cycling produce zero tailpipe CO₂e, but heavy breathing beside traffic in severe smog sharply raises inhaled PM2.5.",
      "During poor or severe pollution, enclosed urban rail/metro or shared transit with a well-fitted N95/FFP2 respirator protects health while still cutting solo-car emissions.",
      "Individual commute switches reduce your personal transport footprint (is_estimate: true) without claiming a measurable drop in city-wide AQI.",
    ],
    bodyParagraphs: [
      "Sustainable mobility tools often rank walking and cycling first regardless of outdoor air conditions. AirWise enforces an explicit exposure-first hierarchy: immediate human respiratory protection comes before transport carbon optimization.",
      "On clean or moderate days, active travel is ideal. During smog episodes, enclosed electric rail or carpooling with cabin air recirculation lowers both personal particulate exposure and per-passenger CO₂e compared with solo petrol driving.",
    ],
    officialReferences: [
      {
        publisher: "NCDC / MoHFW India",
        title: "Health Advisory on Air Pollution",
        url: "https://ncdc.mohfw.gov.in/uploads/pdf/air2.pdf",
      },
    ],
  },
];
