const MAX_TERMS = 8;
const MAX_TERM_LENGTH = 40;


const THAI_STOP_WORDS = new Set([
  "มี", "ราคา", "เท่าไหร่", "เท่าไร", "เท่าไหร่ครับ", "เท่าไหร่คะ", "รถ", "รุ่น", "ที่", "ของ", "ไหม", "ครับ", "ค่ะ", "มีราคา",
]);
const ENGLISH_STOP_WORDS = new Set(["how", "much", "what", "is", "the", "a", "an", "car", "price", "does", "do"]);

function normalize(value: string): string {
  return value.normalize("NFKC").trim().toLocaleLowerCase("th-TH");
}

/** Extract likely catalog names without ever using the whole question as an entity. */
export function extractQuestionTerms(question: string): string[] {
  let text = normalize(question);
  for (const stopWord of [...THAI_STOP_WORDS].filter((word) => word.length > 2).sort((a, b) => b.length - a.length)) {
    text = text.replaceAll(stopWord, " ");
  }

  const latinAndNumber = text.match(/[a-z0-9]+/gi) ?? [];
  const thaiTokens = text.match(/[\u0E00-\u0E7F]+/g) ?? [];
  const terms: string[] = [];
  const seen = new Set<string>();
  for (const term of [...latinAndNumber, ...thaiTokens]) {
    const normalized = normalize(term);
    if (!normalized || normalized.length > MAX_TERM_LENGTH || THAI_STOP_WORDS.has(normalized) || ENGLISH_STOP_WORDS.has(normalized) || seen.has(normalized)) continue;
    seen.add(normalized);
    terms.push(term.match(/^[A-Za-z0-9]+$/) ? term : normalized);
    if (terms.length >= MAX_TERMS) break;
  }
  return terms;
}

export const QUESTION_SEARCH_LIMIT = 8;
