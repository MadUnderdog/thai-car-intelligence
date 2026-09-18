import "dotenv/config";

async function main() {
  console.log("=== Embedding Smoke Test ===\n");
  
  const baseUrl = process.env.EMBEDDING_BASE_URL?.trim();
  const apiKey = process.env.EMBEDDING_API_KEY?.trim();
  const model = process.env.EMBEDDING_MODEL?.trim();
  const dimensions = process.env.EMBEDDING_DIMENSIONS?.trim();
  
  console.log("Config:");
  console.log(`  Base URL: ${baseUrl?.substring(0, 40)}...`);
  console.log(`  Model: ${model}`);
  console.log(`  Expected dimensions: ${dimensions}`);
  console.log("");
  
  if (!baseUrl || !apiKey || !model) {
    console.log("ERROR: Missing embedding configuration");
    return;
  }
  
  // Test 1: Thai automotive query
  console.log("Test 1: Thai automotive query embedding");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/embeddings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        input: "Honda City e:HEV ราคาเท่าไหร่",
      }),
    });
    const latency = Date.now() - start;
    
    console.log(`  Status: ${response.status}`);
    if (response.ok) {
      const data = await response.json();
      const embedding = data.data?.[0]?.embedding;
      console.log(`  Dimensions: ${embedding?.length || "N/A"}`);
      console.log(`  Latency: ${latency}ms`);
      console.log(`  Model: ${data.model || "N/A"}`);
      console.log("  PASS\n");
    } else {
      const text = await response.text();
      console.log(`  Error: ${text.substring(0, 200)}`);
      console.log("  FAIL\n");
    }
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
  
  // Test 2: Vehicle spec text
  console.log("Test 2: Vehicle spec text embedding");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/embeddings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        input: "Honda City e:HEV ราคา 569,000 บาท กำลัง 109 แรงม้า",
      }),
    });
    const latency = Date.now() - start;
    
    console.log(`  Status: ${response.status}`);
    if (response.ok) {
      const data = await response.json();
      const embedding = data.data?.[0]?.embedding;
      console.log(`  Dimensions: ${embedding?.length || "N/A"}`);
      console.log(`  Latency: ${latency}ms`);
      console.log("  PASS\n");
    } else {
      const text = await response.text();
      console.log(`  Error: ${text.substring(0, 200)}`);
      console.log("  FAIL\n");
    }
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
}

main().catch(console.error);
