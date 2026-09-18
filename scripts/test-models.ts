import "dotenv/config";

async function testModel(baseUrl: string, apiKey: string, model: string, name: string) {
  console.log(`\nTest: ${name} (${model})`);
  try {
    const start = Date.now();
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "x-opencode-session": `test-${name}-${Date.now()}`,
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: "Say hello in Thai" }],
        max_tokens: 50,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Content: ${data.choices?.[0]?.message?.content?.substring(0, 100) || "(empty)"}`);
    console.log(`  Reasoning: ${data.choices?.[0]?.message?.reasoning?.substring(0, 50) || "(none)"}`);
    console.log(`  Latency: ${latency}ms`);
    console.log(`  ${response.ok ? "PASS" : "FAIL"}`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}`);
  }
}

async function main() {
  const baseUrl = process.env.AI_BASE_URL?.trim()!;
  const apiKey = process.env.AI_API_KEY?.trim()!;
  
  await testModel(baseUrl, apiKey, "glm-5.3-flash", "glm-5.3-flash");
  await testModel(baseUrl, apiKey, "mimo-v2.5", "mimo-v2.5");
  await testModel(baseUrl, apiKey, "union-alpha", "union-alpha");
}

main().catch(console.error);
