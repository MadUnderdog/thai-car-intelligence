import { NextResponse } from "next/server";
import { z } from "zod";
import { searchQuestionCatalog } from "../../../../../lib/ai/retrieval/catalog-search";

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

    const evidence = variants.map((v) => ({
      id: `variant:${v.id}`,
      kind: "fact" as const,
      content: `${v.manufacturer.nameEn} ${v.nameEn}${v.fuelType ? ` (${v.fuelType})` : ""}`,
      official: true,
      metadata: { variantId: v.id },
    }));

    const vehicleList = variants.map((v) => `- ${v.manufacturer.nameEn} ${v.nameEn} (${v.fuelType ?? "N/A"})`).join("\n");
    const answer = `จากการค้นหาในฐานข้อมูล พบรถที่ตรงกับคำถาม ${variants.length} รุ่น:\n\n${vehicleList}\n\nหากต้องการข้อมูลเพิ่มเติมเรื่องราคา สเปก หรือเปรียบเทียบ สามารถถามได้เพิ่มเติม`;

    return NextResponse.json({
      answer,
      citations: evidence,
      whyThisAnswer: evidence,
      mode: "structured-catalog",
      status: "ok",
      confidence: "partial",
    });
  } catch (error) {
    console.error("API /api/ai/ask error:", error);
    return NextResponse.json({ answer: "ไม่สามารถประมวลผลคำถามได้ กรุณาลองใหม่", citations: [], whyThisAnswer: [], mode: "structured-catalog", status: "unavailable" }, { status: 503 });
  }
}
