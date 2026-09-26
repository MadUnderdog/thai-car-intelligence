import "dotenv/config";
import { searchQuestionCatalog } from "../lib/ai/retrieval/catalog-search";
import { getAIProvider } from "../lib/ai/provider-factory";

async function main() {
  console.log("Testing AI Ask path...\n");
  
  // Test catalog search
  console.log("1. Catalog search for 'Honda':");
  try {
    const variants = await searchQuestionCatalog("Honda");
    console.log(`   Found ${variants.length} variants`);
    if (variants.length > 0) {
      console.log(`   First: ${variants[0].manufacturer.nameEn} ${variants[0].nameEn}`);
    }
  } catch (e: any) {
    console.log(`   Error: ${e.message}`);
  }
  
  // Test AI provider
  console.log("\n2. AI Provider:");
  try {
    const provider = getAIProvider();
    console.log(`   Name: ${provider.name}`);
    console.log(`   Model: ${(provider as any).model || "N/A"}`);
  } catch (e: any) {
    console.log(`   Error: ${e.message}`);
  }
  
  // Test direct AI call
  console.log("\n3. Direct AI call:");
  try {
    const provider = getAIProvider();
    if (provider.name !== "unavailable") {
      const result = await provider.chat({
        question: "Honda City ราคาเท่าไหร่?",
        evidence: [{ id: "1", kind: "fact", content: "Honda City e:HEV ราคา 569,000 บาท" }],
        language: "th",
      });
      console.log(`   Answer: ${result.answer?.substring(0, 100)}`);
      console.log(`   Status: ${result.status}`);
    } else {
      console.log("   Provider unavailable");
    }
  } catch (e: any) {
    console.log(`   Error: ${e.message}`);
  }
}

main().catch(console.error);
