import { describe, expect, it } from "vitest";
import { extractHtmlCandidates } from "../../lib/sources/discovery/html-candidates";
import { scoreBrochureCandidate } from "../../lib/sources/scoring/brochure-score";
import { discoverBrochures } from "../../workers/discovery/brochure-discovery";
import { discoverImages, selectHighestResolutionSrcset } from "../../workers/discovery/image-discovery";

const pageUrl = "https://toyota.co.th/cars/yaris";
const html = `
<a href="/files/yaris-2025-th.pdf" download="Brochure">Yaris brochure</a>
<img data-src="/img/yaris.jpg" alt="Yaris hero">
<img srcset="/img/yaris-small.jpg 400w, /img/yaris-large.jpg 1600w" alt="gallery">
<meta property="og:image" content="/img/og.jpg">
<meta name="twitter:image" content="https://cdn.example/yaris.png">
<script type="application/ld+json">{"image":["/img/json.jpg"]}</script>`;

describe("HTML candidate discovery", () => {
  it("extracts links, lazy images, srcset, metadata, and JSON-LD with resolved URLs", () => {
    const candidates = extractHtmlCandidates(html, pageUrl);
    expect(candidates).toEqual(expect.arrayContaining([
      expect.objectContaining({ kind: "document", url: "https://toyota.co.th/files/yaris-2025-th.pdf", discoveryMethod: "href" }),
      expect.objectContaining({ kind: "image", url: "https://toyota.co.th/img/yaris-large.jpg", width: 1600, discoveryMethod: "srcset" }),
      expect.objectContaining({ url: "https://toyota.co.th/img/og.jpg", discoveryMethod: "og:image" }),
      expect.objectContaining({ url: "https://toyota.co.th/img/json.jpg", discoveryMethod: "json-ld:image" }),
    ]));
  });

  it("selects the highest resolution srcset image", () => {
    const images = discoverImages(html, pageUrl);
    expect(selectHighestResolutionSrcset(images)?.width).toBe(1600);
  });

  it("classifies utility assets as unknown instead of meaningful vehicle thumbnails", () => {
    const images = discoverImages(`<img src="/assets/menu-arrow-small.png" alt="menu icon"><img src="/cars/yaris-thumb.jpg" alt="Yaris side view">`, pageUrl);
    expect(images.find((image) => image.url.endsWith("menu-arrow-small.png"))?.role).toBe("unknown");
    expect(images.find((image) => image.url.endsWith("yaris-thumb.jpg"))?.role).toBe("thumbnail");
  });
});

describe("brochure scoring", () => {
  it("favors official linked Thai model-year PDFs", () => {
    const candidate = extractHtmlCandidates(html, pageUrl).find((item) => item.kind === "document")!;
    const score = scoreBrochureCandidate({ candidate, officialDomains: ["toyota.co.th"], modelName: "Yaris", year: 2025, pageUrl });
    expect(score).toMatchObject({ officialDomain: 30, directPageLinkage: 15, modelName: 25, thaiOrThailand: 10, year: 10 });
    expect(score.total).toBeGreaterThan(80);
  });

  it("does not count a substring as a model match", () => {
    const candidate = { url: "https://toyota.co.th/files/yaris-cross.pdf", sourcePageUrl: pageUrl, kind: "document" as const };
    expect(scoreBrochureCandidate({ candidate, modelName: "Yaris", pageUrl }).modelName).toBe(0);
  });
});

describe("brochure discovery audit", () => {
  it("returns a not_found audit for an empty deterministic pass", () => {
    const result = discoverBrochures([{ url: pageUrl, html: "<p>No downloads</p>" }], { searchedAt: "2026-01-01T00:00:00.000Z", officialDomains: ["toyota.co.th"], queries: ["Yaris brochure"] });
    expect(result.candidates).toHaveLength(0);
    expect(result.audit).toEqual(expect.objectContaining({ status: "not_found", searchedAt: "2026-01-01T00:00:00.000Z", domains: ["toyota.co.th"], queries: ["Yaris brochure"], pagesChecked: [pageUrl] }));
  });
});
