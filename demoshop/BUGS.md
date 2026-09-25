# DemoShop — planted defects

DemoShop is a small e-commerce reference app used to demonstrate PROBE. It is
deliberately imperfect. **None of the defects below are revealed to PROBE** —
the agents have to discover them on their own.

```
Home → Search → Product → Cart → Checkout → Payment → Success
```

## 1. Duplicate payment requests

The pay button is never disabled while a request is in flight and the payment
call carries no idempotency key, so clicking it repeatedly creates one charge
per click.

- `submitPayment()` in `src/data.ts`
- `Checkout` in `src/App.tsx`

## 2. No checkout loading feedback

A payment takes 1.4s (or 6s with `?slow=1`) and the UI shows nothing at all
while it is pending — no spinner, no disabled state, no progress text.

## 3. Search crashes with no recovery path

Any query containing `error`, `fail`, `crash` or `undefined` throws while
rendering the results. The error screen offers a single "Dismiss" action that
does not restore the search.

- `Search` in `src/App.tsx`

## 4. Long input overflows the layout

The review textarea has no `max-length` and no wrapping constraint, so long
values break out of the viewport.

- `ProductPage` in `src/App.tsx`

## 5. Back navigation loses state

Pressing the browser **Back** button away from the cart silently discards its
contents. Forward navigation (cart -> checkout) correctly preserves them, so the
checkout flow stays reachable — it is specifically the back gesture that loses
state.

- the `popstate` listener in `App`

## 6. Slow network causes an unusual checkout state

Appending `?slow=1` (or `#/checkout?slow=1`) stretches the payment to six
seconds, which combined with defects #1 and #2 makes duplicate charges easy.

## Running it

```bash
pnpm --filter @probe/demoshop dev      # http://localhost:5174
```

## Inspecting it with PROBE

```bash
# backend
cd services/api && uv run uvicorn app.main:app --port 8000

# real Chromium (install once)
uv run playwright install chromium

# then point PROBE at http://localhost:5174 from the New inspection screen
```

The built-in simulator (`PROBE_BROWSER_MODE=mock`) reproduces these same defects
without a browser, which is what makes the demo reliable on stage.
