import "dotenv/config";

/**
 * Non-secret config readout — reports active model/provider names without keys.
 */
export function readAIConfig(env = process.env) {
  return {
    defaultModel: env.AI_MODEL?.trim() || "(not set)",
    simpleModel: env.AI_SIMPLE_MODEL?.trim() || "(not set)",
    complexModel: env.AI_COMPLEX_MODEL?.trim() || "(not set)",
    fallbackModel: env.AI_FAST_FALLBACK_MODEL?.trim() || "(not set)",
    embeddingModel: env.EMBEDDING_MODEL?.trim() || "(not set)",
    embeddingDimensions: env.EMBEDDING_DIMENSIONS?.trim() || "(not set)",
    provider: env.AI_PROVIDER?.trim() || "(not set)",
    embeddingProvider: env.EMBEDDING_PROVIDER?.trim() || "(not set)",
    aiKeyPresent: !!env.AI_API_KEY?.trim(),
    embeddingKeyPresent: !!env.EMBEDDING_API_KEY?.trim(),
  };
}

if (require.main === module) {
  const config = readAIConfig();
  console.log("=== AI Config Readout (no secrets) ===\n");
  console.log(`Default model:      ${config.defaultModel}`);
  console.log(`Simple model:       ${config.simpleModel}`);
  console.log(`Complex model:      ${config.complexModel}`);
  console.log(`Fallback model:     ${config.fallbackModel}`);
  console.log(`Embedding model:    ${config.embeddingModel}`);
  console.log(`Embedding dims:     ${config.embeddingDimensions}`);
  console.log(`Provider:           ${config.provider}`);
  console.log(`Embedding provider: ${config.embeddingProvider}`);
  console.log(`AI key present:     ${config.aiKeyPresent ? "yes" : "no"}`);
  console.log(`Embed key present:  ${config.embeddingKeyPresent ? "yes" : "no"}`);
}
