import { describe, expect, it } from "vitest";
import { chunkExtractedText } from "../../workers/indexing/chunker";

describe("document chunker", () => {
  it("keeps page metadata and enforces a deterministic bound", () => {
    const chunks = chunkExtractedText("abcdefgh\fijk", { maxCharacters: 3 });
    expect(chunks.map(({ index, pageNumber, text }) => ({ index, pageNumber, text }))).toEqual([
      { index: 0, pageNumber: 1, text: "abc" },
      { index: 1, pageNumber: 1, text: "def" },
      { index: 2, pageNumber: 1, text: "gh" },
      { index: 3, pageNumber: 2, text: "ijk" },
    ]);
    expect(chunks.every((chunk) => chunk.text.length <= 3 && chunk.contentHash.length === 64)).toBe(true);
  });
});
