import { describe, it, expect } from "vitest";
import { gateStateToConfidence, confidenceLabel, confidenceBadgeVariant } from "../lib/ai/trust-contract";
import type { FactualConfidence } from "../lib/ai/trust-contract";

describe("trust contract", () => {
  describe("gateStateToConfidence", () => {
    it("returns VERIFIED when gate accepted, not qualified, with structured hits", () => {
      expect(gateStateToConfidence(true, false, 3)).toBe("VERIFIED");
    });

    it("returns QUALIFIED when gate accepted but qualified", () => {
      expect(gateStateToConfidence(true, true, 2)).toBe("QUALIFIED");
    });

    it("returns INSUFFICIENT when gate rejected and no structured hits", () => {
      expect(gateStateToConfidence(false, false, 0)).toBe("INSUFFICIENT");
    });

    it("returns VERIFIED when gate rejected but has structured hits", () => {
      expect(gateStateToConfidence(false, false, 1)).toBe("VERIFIED");
    });

    it("returns QUALIFIED when gate accepted, qualified, with no structured hits", () => {
      expect(gateStateToConfidence(true, true, 0)).toBe("QUALIFIED");
    });
  });

  describe("confidenceLabel", () => {
    it("returns Thai labels for all states", () => {
      expect(confidenceLabel("VERIFIED")).toBe("ข้อมูลยืนยันแล้ว");
      expect(confidenceLabel("QUALIFIED")).toBe("ข้อมูลบางส่วน");
      expect(confidenceLabel("INSUFFICIENT")).toBe("ยังไม่มีข้อมูลยืนยัน");
      expect(confidenceLabel("CLARIFICATION_NEEDED")).toBe("กรุณาระบุให้ชัดเจน");
      expect(confidenceLabel("RESEARCH_UNVERIFIED")).toBe("ข้อมูลจากงานวิจัย (ยังไม่ยืนยัน)");
    });
  });

  describe("confidenceBadgeVariant", () => {
    it("returns success for VERIFIED", () => {
      expect(confidenceBadgeVariant("VERIFIED")).toBe("success");
    });

    it("returns warning for QUALIFIED", () => {
      expect(confidenceBadgeVariant("QUALIFIED")).toBe("warning");
    });

    it("returns default for INSUFFICIENT", () => {
      expect(confidenceBadgeVariant("INSUFFICIENT")).toBe("default");
    });
  });

  describe("research never maps to VERIFIED", () => {
    const allStates: FactualConfidence[] = [
      "VERIFIED", "QUALIFIED", "INSUFFICIENT", "CLARIFICATION_NEEDED", "RESEARCH_UNVERIFIED",
    ];
    for (const state of allStates) {
      it(`${state} label does not contain "ยืนยันแล้ว" unless VERIFIED`, () => {
        const label = confidenceLabel(state);
        if (state !== "VERIFIED") {
          expect(label).not.toBe("ข้อมูลยืนยันแล้ว");
        }
      });
    }
  });
});
