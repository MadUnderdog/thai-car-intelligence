/**
 * Body-type / segment intent constraints for automotive queries.
 * Used to prevent wrong-body-type evidence from being ACCEPTED/QUALIFIED
 * when the user explicitly requests a specific vehicle type.
 *
 * These are deterministic, LLM-free classifications derived from known
 * Thai market vehicle segment naming conventions.
 */

/** Canonical body-type tokens (English + Thai) */
export const BODY_TYPE_MAP: Record<string, string> = {
  // English
  "suv": "SUV", "crossover": "SUV",
  "sedan": "sedan",
  "hatchback": "hatchback", "แฮทช์แบ็ก": "hatchback", "แฮทช์": "hatchback",
  "pickup": "pickup", "ปิกอัพ": "pickup", "กระบะ": "pickup",
  "mpv": "MPV", "minivan": "MPV", "มินิแวน": "MPV",
  "coupe": "coupe", "คูเป้": "coupe",
  "wagon": "wagon",
  "van": "van", "ตู้": "van",
  // Thai SUV variants
  "อเนกประสงค์": "SUV",
  "เอสยูวี": "SUV",
  "ครอสโอเวอร์": "SUV",
  // Thai pickup variants
  "รถกระบะ": "pickup",
};

/** Map of known vehicle model slugs to their body types (knowledge-based, not DB) */
export const KNOWN_BODY_TYPES: Record<string, string> = {
  // Honda
  "honda-city": "sedan", "honda-city-hb": "hatchback", "honda-civic": "sedan",
  "honda-civic-tr": "coupe", "honda-cr-v": "SUV", "honda-hr-v": "SUV",
  "honda-br-v": "SUV", "honda-wr-v": "SUV", "honda-accord": "sedan",
  "honda-en2": "sedan", "honda-super-one": "SUV",
  // Toyota
  "toyota-yaris": "hatchback", "toyota-yaris-ativ": "sedan",
  "toyota-corolla-altis": "sedan", "toyota-camry": "sedan",
  "toyota-fortuner": "SUV", "toyota-hilux": "pickup",
  "toyota-yaris-cross": "SUV", "toyota-bz4x": "SUV",
  // MG
  "mg4": "hatchback", "mg-s5": "SUV", "mg-im5": "sedan", "mg-im6": "SUV",
  "mg-zs": "SUV", "mg-zs-ev": "SUV", "mg3-hybrid": "hatchback",
  "mg-hs-phev": "SUV", "mg-urban": "hatchback", "mg-ep": "sedan",
  "mg-es": "sedan", "mg-extender": "pickup", "mg-cyberster": "coupe",
  "mg-maxus7": "MPV", "mg-maxus9": "SUV", "mg-vs-hev": "sedan", "mg5": "sedan",
  // BYD
  "atto-2": "SUV", "atto-3": "SUV", "dolphin": "hatchback",
  "seal": "sedan", "seal-6": "sedan", "sealion-5": "SUV",
  "sealion-6": "SUV", "sealion-7": "SUV", "m6": "SUV",
  // Others
  "denza-z9gt": "wagon", "geely-ex5": "SUV", "gwm-tank-500": "SUV",
  "tesla-model-3": "sedan", "tesla-model-y": "SUV",
  "hyundai-ioniq-5": "SUV", "hyundai-santa-fe": "SUV",
  "nio-firefly": "hatchback", "nissan-kicks": "SUV",
  "subaru-crosstrek": "SUV", "mazda-6e": "sedan",
  "avatr-11": "SUV",
};

export type BodyTypeConstraint = {
  requested: string | null;  // The body type the user explicitly asked for
  match: "strict" | "none";  // strict = must match, none = no body-type constraint
};

/**
 * Extract explicit body-type intent from query text.
 * Returns null if no explicit body type is mentioned.
 */
export function extractBodyType(text: string): string | null {
  const lower = text.toLowerCase();
  const sorted = Object.entries(BODY_TYPE_MAP).sort((a, b) => b[0].length - a[0].length);
  for (const [key, value] of sorted) {
    if (lower.includes(key)) return value;
  }
  return null;
}

/**
 * Given a query and a vehicle's slug, determine whether the body type
 * constraint is satisfied. Returns:
 * - "satisfied": body type matches or no constraint
 * - "violated": body type explicitly conflicts
 * - "unknown": vehicle not in known map (can't determine)
 */
export function checkBodyTypeConstraint(
  queryBodyType: string | null,
  vehicleSlug: string
): "satisfied" | "violated" | "unknown" {
  if (!queryBodyType) return "satisfied"; // no constraint
  const known = KNOWN_BODY_TYPES[vehicleSlug];
  if (!known) return "unknown"; // can't determine
  return known === queryBodyType ? "satisfied" : "violated";
}

/** Model-name-to-body-type mapping (from DB model names). Used for content matching in the gate. */
export const NAME_TO_BODY_TYPE: Record<string, string> = {
  "11": "SUV", "6e": "sedan", "ATTO 2": "SUV", "ATTO 3": "SUV",
  "Accord": "sedan", "BR-V": "SUV", "CR-V": "SUV", "CYBERSTER": "coupe",
  "Camry": "sedan", "City": "sedan", "City Hatchback": "hatchback",
  "Civic": "sedan", "Civic Type R": "coupe", "Corolla Altis": "sedan",
  "Corolla Cross": "SUV", "Crosstrek": "SUV", "Dolphin": "hatchback",
  "EP Plus": "sedan", "ES": "sedan", "EX5": "SUV", "EXTENDER": "pickup",
  "Firefly": "hatchback", "Fortuner": "SUV", "HR-V": "SUV", "HS PHEV": "SUV",
  "Hilux": "pickup", "IM5": "sedan", "IM6": "SUV", "Innova Zenix": "MPV",
  "Ioniq 5": "SUV", "Kicks": "SUV", "L03": "sedan", "M6": "SUV",
  "MAXUS 7": "MPV", "MAXUS 9": "SUV", "MG3 HYBRID+": "hatchback",
  "MG4": "hatchback", "MG5": "sedan", "Model 3": "sedan", "Model Y": "SUV",
  "S5 EV PLUS": "SUV", "Santa Fe": "SUV", "Seal": "sedan", "Seal 6": "sedan",
  "Sealion 5 DM-i": "SUV", "Sealion 6 DM-i": "SUV", "Sealion 7": "SUV",
  "Super-ONE": "SUV", "Tank 500": "SUV", "URBAN": "hatchback",
  "VS HEV": "sedan", "WR-V": "SUV", "X": "SUV", "Yaris": "hatchback",
  "Yaris ATIV": "sedan", "Yaris Cross": "SUV", "Z9GT": "wagon",
  "ZS": "SUV", "ZS EV": "SUV", "bZ4X": "SUV", "e:N2": "sedan",
};
