export type Citation = {
  evidenceId: string;
  sourcePageUrl: string;
  label?: string;
  excerpt?: string;
};

export type EvidenceContext = {
  id: string;
  kind: "fact" | "opinion" | "analysis";
  content: string;
  sourcePageUrl?: string;
  sourceTitle?: string;
  official?: boolean;
  metadata?: Record<string, unknown>;
};

export type ChatInput = {
  question: string;
  evidence: EvidenceContext[];
  language?: "th" | "en";
};

export type ChatOutput = {
  answer: string;
  citations: Citation[];
  status: "ok" | "unavailable" | "insufficient_evidence";
};

export type EmbeddingOutput = {
  embedding: number[];
  model: string;
};

export interface AIProvider {
  readonly name: string;
  chat(input: ChatInput): Promise<ChatOutput>;
  embed(text: string): Promise<EmbeddingOutput>;
}
