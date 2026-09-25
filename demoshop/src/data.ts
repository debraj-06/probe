/** DemoShop catalogue + a fake API with realistic (and flawed) behaviour. */

export interface Product {
  id: string;
  name: string;
  price: number;
  tag: string;
  blurb: string;
}

export const PRODUCTS: Product[] = [
  {
    id: "p1",
    name: "Aurora Wireless Headphones",
    price: 129,
    tag: "audio",
    blurb: "Active noise cancelling, 40 hour battery.",
  },
  {
    id: "p2",
    name: "Nimbus Mechanical Keyboard",
    price: 89.5,
    tag: "desk",
    blurb: "Hot-swappable switches, aluminium frame.",
  },
  {
    id: "p3",
    name: "Vector 4K Webcam",
    price: 74,
    tag: "video",
    blurb: "HDR sensor with automatic framing.",
  },
  {
    id: "p4",
    name: "Halo Desk Lamp",
    price: 42,
    tag: "desk",
    blurb: "Warm to cool tuning with a memory dial.",
  },
  {
    id: "p5",
    name: "Pulse Fitness Band",
    price: 59.99,
    tag: "wearable",
    blurb: "Sleep, heart rate and SpO2 tracking.",
  },
];

export function searchProducts(query: string): Product[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return PRODUCTS;
  return PRODUCTS.filter(
    (product) =>
      product.name.toLowerCase().includes(needle) || product.tag.includes(needle),
  );
}

export function productById(id: string): Product | undefined {
  return PRODUCTS.find((product) => product.id === id);
}

/** Fake network latency, made worse on demand via ?slow=1. */
export function latency(): number {
  const params = new URLSearchParams(window.location.search);
  const hash = window.location.hash.split("?")[1] ?? "";
  const slow =
    params.get("slow") === "1" ||
    new URLSearchParams(hash).get("slow") === "1" ||
    window.location.hash.includes("slow=1");
  return slow ? 6000 : 120;
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export interface PaymentResult {
  ok: boolean;
  orderId: string;
  attempts: number;
  at: string;
}

/**
 * Planted defect #1 + #2 + #6:
 * the payment endpoint has no idempotency key, so every call creates a charge.
 * It is also slow (6s under ?slow=1) while the UI shows nothing at all.
 */
export async function submitPayment(_card: string): Promise<PaymentResult> {
  const wait = latency() * (window.location.hash.includes("slow=1") ? 1 : 12);
  await delay(wait);
  return {
    ok: true,
    orderId: `DS-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    attempts: 1,
    at: new Date().toISOString(),
  };
}
