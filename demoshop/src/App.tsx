import { useCallback, useEffect, useMemo, useState } from "react";

import {
  PRODUCTS,
  delay,
  productById,
  searchProducts,
  submitPayment,
  type PaymentResult,
  type Product,
} from "./data";

/* -------------------------------------------------------------------------- */
/* tiny hash router                                                            */
/* -------------------------------------------------------------------------- */
type Route =
  | { name: "home" }
  | { name: "search"; query: string }
  | { name: "product"; id: string }
  | { name: "cart" }
  | { name: "checkout" }
  | { name: "success" };

function parseRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const [path, search = ""] = hash.split("?");
  const params = new URLSearchParams(search);
  if (path.startsWith("search")) {
    return { name: "search", query: params.get("q") ?? "" };
  }
  if (path.startsWith("product/")) {
    return { name: "product", id: path.slice("product/".length) };
  }
  if (path.startsWith("cart")) return { name: "cart" };
  if (path.startsWith("checkout")) return { name: "checkout" };
  if (path.startsWith("order")) return { name: "success" };
  return { name: "home" };
}

function navigate(to: string) {
  window.location.hash = `#/${to}`;
}

/* -------------------------------------------------------------------------- */
/* app                                                                        */
/* -------------------------------------------------------------------------- */
export default function App() {
  const [route, setRoute] = useState<Route>(parseRoute);
  const [cart, setCart] = useState<Product[]>([]);
  const [payments, setPayments] = useState<PaymentResult[]>([]);

  useEffect(() => {
    const onHashChange = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // keep the document title in step with the route
  useEffect(() => {
    const titles: Record<string, string> = {
      home: "DemoShop — Home",
      search: "DemoShop — Search",
      product: "DemoShop — Product",
      cart: "DemoShop — Cart",
      checkout: "DemoShop — Checkout",
      success: "DemoShop — Order confirmed",
    };
    document.title = titles[route.name] ?? "DemoShop";
  }, [route.name]);

  /**
   * Planted defect #5: navigating away from the cart with the browser Back
   * button throws the cart contents away instead of preserving them.
   *
   * Hash links fire `popstate` too, so the app tracks its own history index in
   * `history.state`: a real back gesture lands on an entry that carries an
   * older index, while a fresh in-app link click has no state yet.
   */
  useEffect(() => {
    const readIndex = (state: unknown): number | null => {
      const value = (state as { probeIndex?: unknown } | null)?.probeIndex;
      return typeof value === "number" ? value : null;
    };
    let index = readIndex(history.state) ?? 0;
    if (readIndex(history.state) === null) {
      history.replaceState({ probeIndex: index }, "");
    }

    const onPopState = (event: PopStateEvent) => {
      const next = readIndex(event.state);
      if (next !== null && next < index && parseRoute().name !== "cart") {
        setCart((current) => (current.length ? [] : current));
      }
      if (next !== null) {
        index = next;
      }
    };
    const onHashChange = () => {
      index += 1;
      history.replaceState({ probeIndex: index }, "");
    };
    window.addEventListener("popstate", onPopState);
    window.addEventListener("hashchange", onHashChange);
    return () => {
      window.removeEventListener("popstate", onPopState);
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);

  const addToCart = useCallback((product: Product) => {
    setCart((current) => [...current, product]);
  }, []);

  const pay = useCallback(async (card: string) => {
    const result = await submitPayment(card);
    setPayments((current) => [...current, result]);
    return result;
  }, []);

  const cartTotal = useMemo(
    () => cart.reduce((total, item) => total + item.price, 0),
    [cart],
  );

  return (
    <div className="app">
      <header className="topbar">
        <a href="#/home" className="brand">
          DemoShop
        </a>
        <nav className="nav">
          <a href="#/home">Home</a>
          <a href="#/search?q=">Search</a>
          <a href="#/cart">Cart ({cart.length})</a>
        </nav>
      </header>

      <main className="content">
        {route.name === "home" ? <Home /> : null}
        {route.name === "search" ? <Search query={route.query} /> : null}
        {route.name === "product" ? (
          <ProductPage id={route.id} onAdd={addToCart} />
        ) : null}
        {route.name === "cart" ? <Cart items={cart} total={cartTotal} /> : null}
        {route.name === "checkout" ? (
          <Checkout items={cart} total={cartTotal} onPay={pay} />
        ) : null}
        {route.name === "success" ? <Success payments={payments} /> : null}
      </main>

      <footer className="footer">
        DemoShop — a deliberately imperfect reference application for PROBE.
      </footer>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* pages                                                                      */
/* -------------------------------------------------------------------------- */
function Home() {
  const [query, setQuery] = useState("");
  return (
    <section>
      <div className="hero">
        <h1>Things that make your desk better</h1>
        <p>Free delivery over $75. 30 day returns.</p>
        <form
          className="search"
          onSubmit={(event) => {
            event.preventDefault();
            navigate(`search?q=${encodeURIComponent(query)}`);
          }}
        >
          <input
            aria-label="Search products"
            placeholder="Search products…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit">Search</button>
        </form>
      </div>

      <h2 className="section-title">Popular</h2>
      <ul className="grid">
        {PRODUCTS.slice(0, 3).map((product) => (
          <li key={product.id} className="card">
            <a href={`#/product/${product.id}`}>
              <div className="thumb" aria-hidden />
              <h3>{product.name}</h3>
            </a>
            <p className="blurb">{product.blurb}</p>
            <p className="price">${product.price.toFixed(2)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Search({ query }: { query: string }) {
  /**
   * Planted defect #3: certain queries crash the results renderer and the only
   * offered action does not recover the search.
   */
  if (/(error|fail|crash|undefined)/i.test(query)) {
    throw new TypeError(
      "Cannot read properties of undefined (reading 'map') at SearchResults (Search.jsx:24:11)",
    );
  }

  const results = searchProducts(query);

  return (
    <section>
      <h1 className="section-title">
        {results.length} result{results.length === 1 ? "" : "s"} for “{query}”
      </h1>
      <ul className="grid">
        {results.map((product) => (
          <li key={product.id} className="card">
            <a href={`#/product/${product.id}`}>
              <div className="thumb" aria-hidden />
              <h3>{product.name}</h3>
            </a>
            <p className="blurb">{product.blurb}</p>
            <p className="price">${product.price.toFixed(2)}</p>
          </li>
        ))}
      </ul>
      {results.length === 0 ? <p className="empty">No products matched.</p> : null}
    </section>
  );
}

function ProductPage({ id, onAdd }: { id: string; onAdd: (product: Product) => void }) {
  const product = productById(id);
  const [review, setReview] = useState("");
  const [submitted, setSubmitted] = useState(false);

  if (!product) {
    return <p className="empty">That product no longer exists.</p>;
  }

  return (
    <section className="product">
      <div className="thumb large" aria-hidden />
      <div>
        <h1>{product.name}</h1>
        <p className="blurb">{product.blurb}</p>
        <p className="price big">${product.price.toFixed(2)}</p>
        <button className="primary" onClick={() => onAdd(product)}>
          Add to cart
        </button>

        <div className="reviews">
          <h2>Write a review</h2>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              await delay(140);
              setSubmitted(true);
            }}
          >
            {/* planted defect #4: no max length, no wrapping constraint */}
            <textarea
              aria-label="Write a review"
              placeholder="Write a review…"
              rows={4}
              value={review}
              onChange={(event) => setReview(event.target.value)}
            />
            <button type="submit">Submit review</button>
          </form>
          {submitted ? <p className="ok">Thanks for your review!</p> : null}
        </div>
      </div>
    </section>
  );
}

function Cart({ items, total }: { items: Product[]; total: number }) {
  if (items.length === 0) {
    return (
      <section>
        <h1 className="section-title">Your cart</h1>
        <p className="empty">Your cart is empty.</p>
        <a className="primary" href="#/home">
          Continue shopping
        </a>
      </section>
    );
  }

  return (
    <section>
      <h1 className="section-title">Your cart</h1>
      <ul className="cart">
        {items.map((item, index) => (
          <li key={`${item.id}-${index}`}>
            <span>{item.name}</span>
            <span className="price">${item.price.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <p className="total">Total: ${total.toFixed(2)}</p>
      <a className="primary" href="#/checkout">
        Checkout
      </a>
    </section>
  );
}

function Checkout({
  items,
  total,
  onPay,
}: {
  items: Product[];
  total: number;
  onPay: (card: string) => Promise<PaymentResult>;
}) {
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [card, setCard] = useState("");
  const [pending, setPending] = useState(false);

  if (items.length === 0) {
    return (
      <section>
        <h1 className="section-title">Checkout</h1>
        <p className="empty">Your cart is empty.</p>
        <a className="primary" href="#/home">
          Continue shopping
        </a>
      </section>
    );
  }

  /**
   * Planted defect #1 + #2: the button is never disabled and no progress is
   * shown, so an impatient user fires several payment requests.
   */
  const handlePay = async () => {
    setPending(true);
    try {
      await onPay(card);
      navigate("order/confirmed");
    } catch {
      setPending(false);
    }
  };

  return (
    <section className="checkout">
      <h1 className="section-title">Checkout</h1>
      <p className="total">Total: ${total.toFixed(2)}</p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handlePay();
        }}
      >
        <label>
          Full name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Address
          <input value={address} onChange={(event) => setAddress(event.target.value)} />
        </label>
        <label>
          Card number
          <input
            value={card}
            onChange={(event) => setCard(event.target.value)}
            placeholder="4242 4242 4242 4242"
          />
        </label>

        <button type="submit" className="primary pay">
          {pending ? "Pay now" : "Pay now"}
        </button>
      </form>
    </section>
  );
}

function Success({ payments }: { payments: PaymentResult[] }) {
  return (
    <section>
      <h1 className="section-title">Thank you!</h1>
      <p>Your order is confirmed.</p>
      {payments.length > 0 ? (
        <p className="price big">
          Payment requests received: {payments.length}
        </p>
      ) : null}
      <a className="primary" href="#/home">
        Back to home
      </a>
    </section>
  );
}
