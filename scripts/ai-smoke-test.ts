// AI Provider Smoke Test
import "dotenv/config";

async function main() {
  console.log("=== AI Provider Smoke Test ===\n");
  
  const baseUrl = process.env.AI_BASE_URL?.trim();
  const apiKey = process.env.AI_API_KEY?.trim();
  const model = process.env.AI_COMPLEX_MODEL?.trim() || "glm-5.3-flash";
  
  if (!baseUrl || !apiKey) {
    console.log("ERROR: AI_BASE_URL or AI_API_KEY not configured");
    return;
  }
  
  console.log("Config:");
  console.log(`  Base URL: ${baseUrl?.substring(0, 40)}...`);
  console.log(`  Model: ${model}`);
  console.log("");
  
  // Test 1: Simple generation
  console.log("Test 1: Simple generation");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "x-opencode-session": "smoke-test-1",
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: "Say hello in Thai" }],
        max_tokens: 50,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Content: ${content?.substring(0, 100)}`);
    console.log(`  Latency: ${latency}ms`);
    console.log(`  Tokens: ${data.usage?.total_tokens || "N/A"}`);
    console.log(`  ${response.ok && content ? "PASS" : "FAIL"}\n`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
  
  // Test 2: Thai car price question
  console.log("Test 2: Thai car price question with evidence");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "x-opencode-session": "smoke-test-2",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "Answer only from the supplied evidence. If evidence is insufficient, say so." },
          { role: "user", content: "Honda City e:HEV ราคาเท่าไหร่?\nEvidence: Honda City e:HEV ราคา 569,000 บาท" },
        ],
        max_tokens: 100,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Content: ${content?.substring(0, 200)}`);
    console.log(`  Latency: ${latency}ms`);
    console.log(`  Tokens: ${data.usage?.total_tokens || "N/A"}`);
    console.log(`  ${response.ok && content ? "PASS" : "FAIL"}\n`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
  
  // Test 3: Comparison question
  console.log("Test 3: Comparison question");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "x-opencode-session": "smoke-test-3",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "Compare the vehicles based on evidence. Be concise." },
          { role: "user", content: "เปรียบเทียบ Honda City และ Honda Civic\nEvidence: Honda City e:HEV ราคา 569,000 บาท กำลัง 109 แรงม้า\nHonda Civic e:HEV ราคา 949,000 บาท กำลัง 141 แรงม้า" },
        ],
        max_tokens: 150,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Content: ${content?.substring(0, 300)}`);
    console.log(`  Latency: ${latency}ms`);
    console.log(`  Tokens: ${data.usage?.total_tokens || "N/A"}`);
    console.log(`  ${response.ok && content ? "PASS" : "FAIL"}\n`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
  
  // Test 4: Unsupported fact
  console.log("Test 4: Unsupported fact handling");
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "x-opencode-session": "smoke-test-4",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "Answer only from evidence. If evidence is insufficient, say so." },
          { role: "user", content: "Tesla Model Y ราคาเท่าไหร่ในไทย?\nEvidence: (none)" },
        ],
        max_tokens: 100,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    const content = data.choices?.[0]?.message?.content;
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Content: ${content?.substring(0, 200)}`);
    console.log(`  Latency: ${latency}ms`);
    console.log(`  Tokens: ${data.usage?.total_tokens || "N/A"}`);
    console.log(`  ${response.ok && content ? "PASS" : "FAIL"}\n`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}\n`);
  }
}

main().catch(console.error);
