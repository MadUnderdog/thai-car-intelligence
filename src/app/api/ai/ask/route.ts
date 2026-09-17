import { NextResponse } from "next/server";
import { z } from "zod";
import pool from "@/lib/db-pg";

const schema = z.object({ question: z.string().trim().min(1, "กรุณาระบุคำถาม").max(500, "คำถามยาวเกินไป") });
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ status: "invalid_request", error: "invalid_json" }, { status: 400 }); }
  const parsed = schema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ status: "invalid_request", error: "invalid_question", details: parsed.error.flatten().fieldErrors }, { status: 400 });

  try {
    // Search for relevant vehicles based on keywords in the question
    const keywords = parsed.data.question.toLowerCase().split(/\s+/);
    const searchPattern = keywords.slice(0, 3).map((k: string) => `%${k}%`).join("|");

    const vehicles: any = await pool.query(
      `SELECT v.id, v."nameEn", v."nameTh", v."fuelType",
        m."nameEn" as "mfrName", m."nameTh" as "mfrTh",
        ps."powerKw", ps."torqueNm", ps."rangeKm",
        bs."capacityKwh", cs."acPowerKw", cs."dcPowerKw"
       FROM "Variant" v
       JOIN "CarModel" cm ON cm.id = v."modelId"
       JOIN "Manufacturer" m ON m.id = cm."manufacturerId"
       LEFT JOIN "PerformanceSpec" ps ON ps."variantId" = v.id
       LEFT JOIN "BatterySpec" bs ON bs."variantId" = v.id
       LEFT JOIN "ChargingSpec" cs ON cs."variantId" = v.id
       WHERE v.status = 'ACTIVE' AND (
         v."nameEn" ILIKE ANY($1) OR v."nameTh" ILIKE ANY($1) OR
         m."nameEn" ILIKE ANY($1) OR m."nameTh" ILIKE ANY($1)
       )
       LIMIT 5`,
      [searchPattern.split("|")]
    );

    if (vehicles.rows.length === 0) {
      return NextResponse.json({
        answer: "ไม่พบข้อมูลที่ตรงกับคำถาม กรุณาระบุชื่อรุ่นรถหรือยี่ห้อให้ชัดเจน",
        citations: [],
        whyThisAnswer: [],
        mode: "structured-catalog",
        status: "insufficient_evidence",
      });
    }

    // Build evidence from found vehicles
    const evidence = vehicles.rows.map((v: any) => ({
      id: `variant:${v.id}`,
      kind: "fact" as const,
      content: `${v.mfrName} ${v.nameEn}${v.fuelType ? ` (${v.fuelType})` : ""}${v.powerKw ? ` - ${v.powerKw}kW` : ""}${v.rangeKm ? `, ${v.rangeKm}km range` : ""}`,
      official: true,
      metadata: { variantId: v.id },
    }));

    // Build a simple response based on found data
    const vehicleList = vehicles.rows.map((v: any) => `- ${v.mfrName} ${v.nameEn} (${v.fuelType})`).join("\n");
    const answer = `จากการค้นหาในฐานข้อมูล พบรถที่ตรงกับคำถาม ${vehicles.rows.length} รุ่น:\n\n${vehicleList}\n\nหากต้องการข้อมูลเพิ่มเติมเรื่องราคา สเปก หรือเปรียบเทียบ สามารถถามได้เพิ่มเติม`;

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
