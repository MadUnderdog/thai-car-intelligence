import { NextResponse } from "next/server";
import { z } from "zod";
import { searchQuestionCatalog } from "../../../../../lib/ai/retrieval/catalog-search";
import { getAIProviderForModel, getConfiguredModels } from "../../../../../lib/ai/provider-factory";

const schema = z.object({ question: z.string().trim().min(1, "กรุณาระบุคำถาม").max(500, "คำถามยาวเกินไป") });
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ status: "invalid_request", error: "invalid_json" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ status: "invalid_request", error: "invalid_question", details: parsed.error.flatten().fieldErrors }, { status: 400 });

  try {
    const variants = await searchQuestionCatalog(parsed.data.question);

    if (variants.length === 0) {
      return NextResponse.json({
        answer: "ไม่พบข้อมูลที่ตรวจสอบได้สำหรับคำถามนี้",
        citations: [],
        whyThisAnswer: [],
        mode: "structured-catalog",
        status: "insufficient_evidence",
      });
    }

    // Build evidence from catalog results
    const evidence = variants.map((v) => ({
      id: `variant:${v.id}`,
      kind: "fact" as const,
      content: `${v.manufacturer.nameEn} ${v.nameEn}${v.fuelType ? ` (${v.fuelType})` : ""}${v.prices?.[0] ? ` ราคา ${v.prices[0].amount.toLocaleString()} บาท` : ""}`,
      official: true,
      metadata: { variantId: v.id },
    }));

    // Get configured models and use the complex model for better responses
    const models = getConfiguredModels();
    const provider = getAIProviderForModel(models.complex);
    
    // Check if provider is available (not unavailable)
    if (provider.name === "unavailable") {
      // Fallback to structured catalog response
      const vehicleList = variants.map((v) => `- ${v.manufacturer.nameEn} ${v.nameEn} (${v.fuelType ?? "N/A"})${v.prices?.[0] ? ` ราคา ${v.prices[0].amount.toLocaleString()} บาท` : ""}`).join("\n");
      const answer = `จากการค้นหาในฐานข้อมูล พบรถที่ตรงกับคำถาม ${variants.length} รุ่น:\n\n${vehicleList}\n\nหากต้องการข้อมูลเพิ่มเติมเรื่องราคา สเปก หรือเปรียบเทียบ สามารถถามได้เพิ่มเติม`;

      return NextResponse.json({
        answer,
        citations: evidence,
        whyThisAnswer: evidence,
        mode: "structured-catalog",
        status: "ok",
        confidence: "partial",
      });
    }

    // Use AI provider for enhanced response
    const aiResult = await provider.chat({
      question: parsed.data.question,
      evidence: evidence.map((e) => ({
        id: e.id,
        kind: e.kind,
        content: e.content,
        official: e.official,
      })),
      language: "th",
    });

    return NextResponse.json({
      answer: aiResult.answer,
      citations: evidence,
      whyThisAnswer: evidence,
      mode: "ai-enhanced",
      status: aiResult.status,
      confidence: aiResult.status === "ok" ? "high" : "partial",
    });
  } catch (error) {
    console.error("API /api/ai/ask error:", error);
    return NextResponse.json({ answer: "ไม่สามารถประมวลผลคำถามได้ กรุณาลองใหม่", citations: [], whyThisAnswer: [], mode: "error", status: "unavailable" }, { status: 503 });
  }
}
