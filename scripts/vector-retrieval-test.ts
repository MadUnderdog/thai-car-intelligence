import "dotenv/config";

// Simple in-memory vector store for testing
class SimpleVectorStore {
  private vectors: Array<{ id: string; text: string; vector: number[]; metadata: any }> = [];
  
  async add(id: string, text: string, vector: number[], metadata: any) {
    this.vectors.push({ id, text, vector, metadata });
  }
  
  search(queryVector: number[], topK: number = 3): Array<{ id: string; text: string; score: number; metadata: any }> {
    const results = this.vectors.map(v => ({
      id: v.id,
      text: v.text,
      score: this.cosineSimilarity(queryVector, v.vector),
      metadata: v.metadata,
    }));
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, topK);
  }
  
  private cosineSimilarity(a: number[], b: number[]): number {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }
}

async function getEmbedding(text: string): Promise<number[]> {
  const baseUrl = process.env.EMBEDDING_BASE_URL?.trim()!;
  const apiKey = process.env.EMBEDDING_API_KEY?.trim()!;
  const model = process.env.EMBEDDING_MODEL?.trim()!;
  
  const response = await fetch(`${baseUrl}/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model, input: text }),
  });
  
  const data = await response.json();
  return data.data?.[0]?.embedding || [];
}

async function main() {
  console.log("=== Vector Retrieval Smoke Test ===\n");
  
  // Controlled corpus of Thai automotive facts
  const corpus = [
    { id: "honda-city-1", text: "Honda City e:HEV ราคา 569,000 บาท กำลัง 109 แรงม้า", metadata: { type: "price", verified: true } },
    { id: "honda-civic-1", text: "Honda Civic e:HEV ราคา 949,000 บาท กำลัง 141 แรงม้า", metadata: { type: "price", verified: true } },
    { id: "honda-hrv-1", text: "Honda HR-V e:HEV ราคา 899,000 บาท กำลัง 131 แรงม้า", metadata: { type: "price", verified: true } },
    { id: "mg4-1", text: "MG4 Standard ราคา 699,900 บาท แบตเตอรี่ 51 kWh ระยะทาง 350 km", metadata: { type: "price", verified: true } },
    { id: "mg-im5-1", text: "MG IM5 EV ราคา 1,549,900 บาท แบตเตอรี่ 77 kWh ชาร์จ DC 150 kW", metadata: { type: "price", verified: true } },
    { id: "byd-atto3-1", text: "BYD Atto 3 ราคา 669,900 บาท แบตเตอรี่ 49.9 kWh ระยะทาง 310 km", metadata: { type: "price", verified: true } },
    { id: "honda-city-spec", text: "Honda City e:HEV ขนาด 4589x1748x1467 mm ฐานล้อ 2610 mm ระยะต่ำสุด 135 mm", metadata: { type: "spec", verified: true } },
    { id: "honda-civic-spec", text: "Honda Civic e:HEV ขนาด 4674x1802x1415 mm ฐานล้อ 2735 mm ระยะต่ำสุด 135 mm", metadata: { type: "spec", verified: true } },
    { id: "mg4-spec", text: "MG4 Standard ขนาด 4287x1836x1516 mm ระยะต่ำสุด 150 mm", metadata: { type: "spec", verified: true } },
    { id: "honda-city-warranty", text: "Honda City e:HEV ประกัน 5 ปี 150,000 km", metadata: { type: "warranty", verified: true } },
  ];
  
  const store = new SimpleVectorStore();
  
  // Index corpus
  console.log("Indexing corpus...");
  for (const item of corpus) {
    const vector = await getEmbedding(item.text);
    await store.add(item.id, item.text, vector, item.metadata);
    console.log(`  Indexed: ${item.id}`);
  }
  console.log("");
  
  // Test queries
  const queries = [
    { query: "Honda City ราคาเท่าไหร่", expected: "honda-city-1" },
    { query: "MG4 แบตเตอรี่กี่ kWh", expected: "mg4-1" },
    { query: "เปรียบเทียบ Honda City กับ Civic", expected: "honda-city-1" },
    { query: "BYD Atto 3 ระยะทางวิ่งได้เท่าไหร่", expected: "byd-atto3-1" },
    { query: "MG IM5 ชาร์จเร็วกี่ kW", expected: "mg-im5-1" },
  ];
  
  let passed = 0;
  let failed = 0;
  
  for (const { query, expected } of queries) {
    console.log(`Query: "${query}"`);
    const queryVector = await getEmbedding(query);
    const results = store.search(queryVector, 3);
    
    console.log(`  Top result: ${results[0]?.id} (score: ${results[0]?.score?.toFixed(4)})`);
    console.log(`  Expected: ${expected}`);
    
    if (results[0]?.id === expected) {
      console.log("  PASS\n");
      passed++;
    } else {
      console.log("  FAIL\n");
      failed++;
    }
  }
  
  console.log(`Results: ${passed}/${passed + failed} passed`);
}

main().catch(console.error);
