export type SourceAdapterType = "html" | "pdf" | "browser" | "press_release" | "structured_data";

export type SourceAdapter = {
  type: SourceAdapterType;
  name: string;
  isAvailable: () => Promise<boolean>;
  canHandle: (url: string) => boolean;
};

const adapters: SourceAdapter[] = [
  {
    type: "html",
    name: "Official HTML",
    isAvailable: async () => true,
    canHandle: (url) => url.endsWith(".html") || url.endsWith("/"),
  },
  {
    type: "pdf",
    name: "Official PDF",
    isAvailable: async () => true,
    canHandle: (url) => url.endsWith(".pdf"),
  },
  {
    type: "browser",
    name: "Browser Extraction",
    isAvailable: async () => {
      // Check if browser is available
      try {
        const res = await fetch("http://127.0.0.1:3015", { signal: AbortSignal.timeout(2000) });
        return res.ok;
      } catch {
        return false;
      }
    },
    canHandle: () => true, // fallback for JS-rendered pages
  },
  {
    type: "press_release",
    name: "Press Release",
    isAvailable: async () => true,
    canHandle: (url) => url.includes("news") || url.includes("press") || url.includes("release"),
  },
  {
    type: "structured_data",
    name: "Structured Data/API",
    isAvailable: async () => true,
    canHandle: (url) => url.includes("api") || url.includes("json"),
  },
];

export async function getAvailableAdapters(): Promise<SourceAdapter[]> {
  const available: SourceAdapter[] = [];
  for (const adapter of adapters) {
    if (await adapter.isAvailable()) {
      available.push(adapter);
    }
  }
  return available;
}

export async function selectAdapter(url: string): Promise<SourceAdapter | null> {
  const available = await getAvailableAdapters();
  // First try adapters that can handle this specific URL
  for (const adapter of available) {
    if (adapter.canHandle(url)) return adapter;
  }
  // Fallback to browser if available
  const browser = available.find((a) => a.type === "browser");
  return browser ?? null;
}

export async function getAdapterStatus(): Promise<{ type: string; name: string; available: boolean }[]> {
  return Promise.all(
    adapters.map(async (a) => ({
      type: a.type,
      name: a.name,
      available: await a.isAvailable(),
    }))
  );
}
