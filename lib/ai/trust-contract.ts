/**
 * Unified factual confidence/state contract for the Thai Car Intelligence platform.
 * Used by AI Ask, detail page, compare, and community research handoff.
 *
 * States:
 * - VERIFIED: Official source, confirmed fact (price from manufacturer site, spec from official brochure)
 * - QUALIFIED: Evidence exists but confidence/coverage is limited (vector match beyond strict threshold, brand-coherent but not exact)
 * - INSUFFICIENT: No trustworthy evidence found
 * - CLARIFICATION_NEEDED: User intent/entity constraint is ambiguous
 * - RESEARCH_UNVERIFIED: Community/research observation, NOT verified against official source
 */

export type FactualConfidence =
  | "VERIFIED"
  | "QUALIFIED"
  | "INSUFFICIENT"
  | "CLARIFICATION_NEEDED"
  | "RESEARCH_UNVERIFIED";

/** Metadata attached to every factual response */
export type ProvenanceMeta = {
  confidence: FactualConfidence;
  /** Whether the response came from structured catalog, vector retrieval, or both */
  retrievalMode: "structured-catalog" | "vector-evidence" | "ai-enhanced";
  /** Number of verified evidence items backing this response */
  verifiedEvidenceCount: number;
  /** Number of qualified (limited confidence) evidence items */
  qualifiedEvidenceCount: number;
  /** Whether any research-only observations are present */
  hasResearchObservations: boolean;
  /** Source URLs / document references */
  sources?: Array<{ url: string; title?: string; status?: string }>;
};

/** Vehicle detail trust state per field group */
export type FieldTrustState = {
  price: FactualConfidence;
  performance: FactualConfidence;
  battery: FactualConfidence;
  charging: FactualConfidence;
  dimensions: FactualConfidence;
  warranty: FactualConfidence;
};

/** Compare cell trust marker */
export type CompareCellTrust = {
  value: string | null;
  confidence: FactualConfidence;
  sourceUrl?: string;
};

/**
 * Map from internal evidence gate state to public trust contract.
 * Gate "accepted" at strict distance → VERIFIED
 * Gate "accepted" at wide distance → QUALIFIED
 * Gate rejected → INSUFFICIENT
 */
export function gateStateToConfidence(
  gateAccepted: boolean,
  qualified: boolean,
  structuredHitCount: number
): FactualConfidence {
  if (!gateAccepted && structuredHitCount === 0) return "INSUFFICIENT";
  if (qualified) return "QUALIFIED";
  if (gateAccepted || structuredHitCount > 0) return "VERIFIED";
  return "INSUFFICIENT";
}

/**
 * Determine display label in Thai for a confidence state.
 */
export function confidenceLabel(c: FactualConfidence): string {
  switch (c) {
    case "VERIFIED": return "ข้อมูลยืนยันแล้ว";
    case "QUALIFIED": return "ข้อมูลบางส่วน";
    case "INSUFFICIENT": return "ยังไม่มีข้อมูลยืนยัน";
    case "CLARIFICATION_NEEDED": return "กรุณาระบุให้ชัดเจน";
    case "RESEARCH_UNVERIFIED": return "ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน)";
  }
}

/**
 * Determine display badge variant for a confidence state.
 */
export function confidenceBadgeVariant(c: FactualConfidence): "success" | "warning" | "default" | "danger" {
  switch (c) {
    case "VERIFIED": return "success";
    case "QUALIFIED": return "warning";
    case "INSUFFICIENT": return "default";
    case "CLARIFICATION_NEEDED": return "default";
    case "RESEARCH_UNVERIFIED": return "default";
  }
}
