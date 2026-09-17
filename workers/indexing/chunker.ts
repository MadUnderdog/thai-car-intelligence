import { createHash } from "node:crypto";

export type DocumentChunk = {
  index: number;
  text: string;
  contentHash: string;
  chunkType: "text";
  pageNumber?: number;
};

export type ChunkOptions = { maxCharacters?: number };

/** Deterministically splits extracted text into bounded, page-aware chunks. */
export function chunkExtractedText(text: string, options: ChunkOptions = {}): DocumentChunk[] {
  const maxCharacters = options.maxCharacters ?? 2_000;
  if (!Number.isInteger(maxCharacters) || maxCharacters < 1) throw new Error("maxCharacters must be a positive integer");
  const pages = text.split("\f");
  const chunks: DocumentChunk[] = [];
  for (let pageIndex = 0; pageIndex < pages.length; pageIndex += 1) {
    const page = pages[pageIndex].trim();
    if (!page) continue;
    let cursor = 0;
    while (cursor < page.length) {
      const end = Math.min(cursor + maxCharacters, page.length);
      const piece = page.slice(cursor, end).trim();
      if (piece) {
        chunks.push({
          index: chunks.length,
          text: piece,
          contentHash: createHash("sha256").update(piece, "utf8").digest("hex"),
          chunkType: "text",
          pageNumber: pageIndex + 1,
        });
      }
      cursor = end;
    }
  }
  return chunks;
}
