import type { EvidenceContext } from "./types";

export type EvidenceConfidence = "verified" | "partial" | "insufficient";

export type EvidenceGateResult = {
  confidence: EvidenceConfidence;
  hasPriceEvidence: boolean;
  hasSpecEvidence: boolean;
  hasVariantEvidence: boolean;
  officialSourceCount: number;
  totalEvidenceCount: number;
  missingDataDescription: string[];
};

const VEHICLE_FACT_PATTERNS = [
  /ราคา/,
  /บาท/,
  /THB/,
  /กม/,
  /km/,
  /แรงม้า/,
  /hp/,
  /kWh/,
  /นิวตัน/,
  /Nm/,
  /kW/,
  /วินาที/,
  /ที่นั่ง/,
  /มิติ/,
  /ความยาว/,
  /ความกว้าง/,
  /ระยะล้อ/,
];

function hasVehicleFact(content: string): boolean {
  return VEHICLE_FACT_PATTERNS.some((p) => p.test(content));
}

/** Check whether retrieved evidence is sufficient to answer automotive questions. */
export function evaluateEvidenceGate(evidence: EvidenceContext[]): EvidenceGateResult {
  const missingDataDescription: string[] = [];

  const priceEvidence = evidence.filter((e) => e.content.includes("ราคา") || /THB|บาท|\d{4,}/.test(e.content));
  const variantEvidence = evidence.filter((e) => e.id.startsWith("variant:"));
  const officialEvidence = evidence.filter((e) => e.official === true);
  const vehicleFactEvidence = evidence.filter((e) => hasVehicleFact(e.content));

  const hasPriceEvidence = priceEvidence.length > 0;
  const hasVariantEvidence = variantEvidence.length > 0;
  const hasSpecEvidence = vehicleFactEvidence.length > priceEvidence.length;

  if (!hasVariantEvidence) missingDataDescription.push("ไม่พบรุ่นรถที่ตรงกับคำถาม");
  if (!hasPriceEvidence) missingDataDescription.push("ไม่พบข้อมูลราคา");
  if (!hasSpecEvidence) missingDataDescription.push("ไม่พบข้อมูลสเปกหรือตัวเลขเทคนิค");

  let confidence: EvidenceConfidence;
  if (hasVariantEvidence && hasPriceEvidence && officialEvidence.length > 0) {
    confidence = "verified";
  } else if (hasVariantEvidence || hasPriceEvidence) {
    confidence = "partial";
  } else {
    confidence = "insufficient";
  }

  return {
    confidence,
    hasPriceEvidence,
    hasSpecEvidence,
    hasVariantEvidence,
    officialSourceCount: officialEvidence.length,
    totalEvidenceCount: evidence.length,
    missingDataDescription,
  };
}

/** Build the fabrication guard response when evidence is insufficient. */
export function buildInsufficientEvidenceResponse(question: string, gate: EvidenceGateResult): {
  answer: string;
  confidence: EvidenceConfidence;
  missingData: string[];
} {
  const reasons = gate.missingDataDescription.length > 0
    ? gate.missingDataDescription.join("; ")
    : "หลักฐานไม่เพียงพอสำหรับคำถามนี้";

  return {
    answer: `ไม่พบข้อมูลยืนยันสำหรับคำถามนี้ ${reasons} กรุณาระบุชื่อรุ่นรถให้ชัดเจน หรือลองค้นหาด้วยคำที่เฉพาะเจาะจงกว่านี้`,
    confidence: "insufficient",
    missingData: gate.missingDataDescription,
  };
}
