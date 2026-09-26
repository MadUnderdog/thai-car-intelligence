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
        "x-opencode-session": `test2-${name}-${Date.now()}`,
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: "Answer in Thai. Be concise." },
          { role: "user", content: "Honda City ราคาเท่าไหร่?" },
        ],
        max_tokens: 100,
      }),
    });
    const latency = Date.now() - start;
    const data = await response.json();
    
    console.log(`  Status: ${response.status}`);
    console.log(`  Full response: ${JSON.stringify(data.choices?.[0]?.message, null, 2).substring(0, 300)}`);
    console.log(`  Latency: ${latency}ms`);
  } catch (e: any) {
    console.log(`  Error: ${e.message}`);
  }
}

async function main() {
  const baseUrl = process.env.AI_BASE_URL?.trim()!;
  const apiKey = process.env.AI_API_KEY?.trim()!;
  
  await testModel(baseUrl, apiKey, "glm-5.3-flash", "glm-5.3-flash");
  await testModel(baseUrl, apiKey, "mimo-v2.5", "mimo-v2.5");
}

main().catch(console.error);
