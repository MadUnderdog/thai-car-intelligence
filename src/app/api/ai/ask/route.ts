import { NextResponse } from "next/server";
import { z } from "zod";
import { searchQuestionCatalog } from "../../../../../lib/ai/retrieval/catalog-search";
import { getAIProviderForModel, getConfiguredModels } from "../../../../../lib/ai/provider-factory";
import { mergeEvidence, getVectorEvidence, type EvidenceItem } from "../../../../../lib/ai/retrieval/evidence-merge";
import { evaluateEvidenceGate } from "../../../../../lib/ai/evidence-gate";
import { parseAutomotiveQuery } from "../../../../../lib/ai/retrieval/query-parser";

const schema = z.object({ question: z.string().trim().min(1, "กรุณาระบุคำถาม").max(500, "คำถามยาวเกินไป") });
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ status: "invalid_request", error: "invalid_json" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ status: "invalid_request", error: "invalid_question", details: parsed.error.flatten().fieldErrors }, { status: 400 });

  try {
    const question = parsed.data.question;
    const intent = parseAutomotiveQuery(question);

    // 1. Structured catalog retrieval
    const variants = await searchQuestionCatalog(question);

    // 2. Vector evidence retrieval (supplemental, threshold-gated)
    const vectorResult = await getVectorEvidence(question);

    // 3. Build structured evidence from catalog
    const structuredEvidence: EvidenceItem[] = variants.map((v) => ({
      id: `variant:${v.id}`,
      kind: "fact" as const,
      content: `${v.manufacturer.nameEn} ${v.nameEn}${v.fuelType ? ` (${v.fuelType})` : ""}${v.prices?.[0] ? ` ราคา ${v.prices[0].amount.toLocaleString()} บาท` : ""}`,
      official: true,
      metadata: { variantId: v.id },
    }));

    // 4. Merge structured + vector evidence
    const merged = mergeEvidence(structuredEvidence, vectorResult);

    // 4b. Ambiguity check: compare-intent or no-entity query with many different
    // vehicles retrieved → clarify instead of answering confidently.
    if (intent.type === "compare" && merged.merged.length < 2) {
      return NextResponse.json({
        answer: "ไม่พบข้อมูลครบทั้งสองรุ่นที่ต้องการเปรียบเทียบ กรุณาระบุชื่อรุ่นรถให้ชัดเจน",
        citations: merged.merged,
        whyThisAnswer: merged.merged,
        mode: "structured-catalog",
        status: "insufficient_evidence",
        vectorAvailable: merged.vectorAvailable,
      });
    }

    // 4c. No structured hit, and vector evidence referencing entities not in the query
    // (gate already dropped uncorroborated rows) → insufficient evidence.
    if (merged.merged.length === 0) {
      return NextResponse.json({
        answer: "ไม่พบข้อมูลที่ตรวจสอบได้สำหรับคำถามนี้",
        citations: [],
        whyThisAnswer: [],
        mode: "structured-catalog",
        status: "insufficient_evidence",
        vectorAvailable: merged.vectorAvailable,
      });
    }

    // 5. Evidence Gate (existing)
    const gate = evaluateEvidenceGate(merged.merged.map((e) => ({
      id: e.id,
      kind: e.kind,
      content: e.content,
      official: e.official,
    })));

    // 5b. Confidence qualification: vector rows retrieved beyond the strict
    // nearest-neighbor threshold are carried as qualified context only.
    const qualifiedVectorIds = new Set(
      merged.vector.filter((v) => (v as { qualified?: boolean }).qualified).map((v) => `vector:${v.id}`)
    );
    const qualifiedEvidence = merged.merged.filter((e) => qualifiedVectorIds.has(e.id));

    // 6. Get AI provider
    const models = getConfiguredModels();
    const provider = getAIProviderForModel(models.complex);

    // 7. Check if provider is available
    if (provider.name === "unavailable") {
      const vehicleList = variants.map((v) => `- ${v.manufacturer.nameEn} ${v.nameEn} (${v.fuelType ?? "N/A"})${v.prices?.[0] ? ` ราคา ${v.prices[0].amount.toLocaleString()} บาท` : ""}`).join("\n");
      const answer = `จากการค้นหาในฐานข้อมูล พบรถที่ตรงกับคำถาม ${variants.length} รุ่น:\n\n${vehicleList}\n\nหากต้องการข้อมูลเพิ่มเติมเรื่องราคา สเปก หรือเปรียบเทียบ สามารถถามได้เพิ่มเติม`;

      return NextResponse.json({
        answer,
        citations: merged.merged,
        whyThisAnswer: merged.merged,
        mode: "structured-catalog",
        status: "ok",
        confidence: gate.confidence,
        vectorAvailable: merged.vectorAvailable,
      });
    }

    // 8. Duplicate-retrieval fix: detached structured price list already covers the
    // catalog finding; ask only question + merged evidence (vector rows carry facts
    // that structured rows omit — specs). The gate result is passed as guidance so
    // the model qualifies its answer when evidence is partial.
    const gatePrefix =
      gate.confidence === "insufficient" ? "(หลักฐานไม่เพียงพอ จะไม่ตอบเกินหลักฐานที่มี)"
      : gate.confidence === "partial" ? "(หลักฐานบางส่วน หากข้อมูลไม่ครบตามคำถามให้บอกว่าไม่มี)"
      : qualifiedEvidence.length > 0 ? "(หลักฐานบางส่วนเป็นการคาดเดาจากการค้นหาแบบความมั่นใจต่ำ ให้ระบุว่าข้อมูลนั้นอาจไม่ตรงคำถามและแนะนำให้ระบุรุ่นที่แน่นอน)"
      : "";

    const aiResult = await provider.chat({
      question: `${gatePrefix ? gatePrefix + " " : ""}${question}`,
      evidence: merged.merged.map((e) => ({
        id: e.id,
        kind: e.kind,
        content: e.content,
        official: e.official,
      })),
      language: "th",
    });

    return NextResponse.json({
      answer: aiResult.answer,
      citations: merged.merged,
      whyThisAnswer: merged.merged,
      mode: "ai-enhanced",
      status: aiResult.status,
      confidence: aiResult.status === "ok" ? gate.confidence : "partial",
      vectorAvailable: merged.vectorAvailable,
      vectorEvidenceCount: merged.vector.length,
    });
  } catch (error) {
    console.error("API /api/ai/ask error:", error);
    return NextResponse.json({ answer: "ไม่สามารถประมวลผลคำถามได้ กรุณาลองใหม่", citations: [], whyThisAnswer: [], mode: "error", status: "unavailable" }, { status: 503 });
  }
}
