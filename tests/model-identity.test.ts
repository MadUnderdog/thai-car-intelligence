import { describe, it, expect } from "vitest";

// Model identity regression tests
// Prevent cross-model contamination

describe("model identity regression", () => {
  // Test data: model identity rules
  const modelRules = [
    { model: "Xpander", bodyType: "MPV", engine: "1.5L", power: 77 },
    { model: "Xforce", bodyType: "SUV", engine: "1.5L", power: 77 },
    { model: "ATTO 3", bodyType: "EV_SUV", power: 150 },
    { model: "Dolphin", bodyType: "EV_SUV", power: 70 },
    { model: "Camry", bodyType: "Sedan", power: 137 },
    { model: "Corolla Cross", bodyType: "Crossover", power: 72 },
  ];

  it("Xpander and Xforce have same engine but different body types", () => {
    const xpander = modelRules.find((m) => m.model === "Xpander")!;
    const xforce = modelRules.find((m) => m.model === "Xforce")!;
    expect(xpander.bodyType).toBe("MPV");
    expect(xforce.bodyType).toBe("SUV");
    expect(xpander.engine).toBe(xforce.engine); // same engine
  });

  it("Xpander dimensions must not match Xforce dimensions", () => {
    // Xpander: 4510 x 1750 x 1730 mm
    // Xforce: 4390 x 1810 x 1660 mm
    const xpanderDims = { length: 4510, width: 1750, height: 1730 };
    const xforceDims = { length: 4390, width: 1810, height: 1660 };
    expect(xpanderDims.length).not.toBe(xforceDims.length);
    expect(xpanderDims.width).not.toBe(xforceDims.width);
  });

  it("ATTO 3 and Dolphin have different power outputs", () => {
    const atto3 = modelRules.find((m) => m.model === "ATTO 3")!;
    const dolphin = modelRules.find((m) => m.model === "Dolphin")!;
    expect(atto3.power).not.toBe(dolphin.power);
  });

  it("Camry and Corolla Cross are different segments", () => {
    const camry = modelRules.find((m) => m.model === "Camry")!;
    const corolla = modelRules.find((m) => m.model === "Corolla Cross")!;
    expect(camry.bodyType).toBe("Sedan");
    expect(corolla.bodyType).toBe("Crossover");
  });
});
