# Design — WhatsApp AI Receptionist Dashboard

Direction for `frontend/`: leaner visual language, purposeful motion.

**Status (2026-07-07): sections 1-4 below are implemented**, using a
concrete Material 3 token set (extracted from a Stitch-generated reference,
`primary #006856`) instead of the original abstract oklch proposal. What
shipped:
- `tailwind.config.ts` / `globals.css`: M3 color tokens as space-separated
  RGB channels (`rgb(var(--x) / <alpha-value>)`) so opacity modifiers work;
  shadcn's own token names (`primary`, `muted`, `border`, etc.) kept for
  component compatibility, M3 surface-container/outline/tertiary scale added
  alongside for custom UI.
- Material Symbols Outlined (variable font) + a small `<Icon>` component
  (`components/ui/icon.tsx`, `aria-hidden` by default since icons are always
  paired with visible text in this app).
- Sidebar/header redesign: rounded-r-full active nav indicator, user card
  with initials (new `GET /auth/me` endpoint), live-status pulse badge
  wired to real `/settings/status` data.
- Conversations rebuilt as a split-pane (persistent list + thread), using a
  nested layout + React context so the list doesn't re-fetch on navigation
  between threads. Message bubbles, avatars (hashed color per contact),
  status badges all styled per the M3 reference.
- New `POST /conversations/{id}/reply` endpoint for human takeover — added
  because the reference's reply box would otherwise be a dead UI element;
  sending a manual reply sets `conversation.status = human`, which the
  worker's existing handoff-is-sacred check already respects.
- New `/dashboard` overview page: stat cards and recent-activity list built
  from real `/conversations` + `/leads` data only. Deliberately omits the
  reference's charts (conversation volume, lead sources) and metrics like
  "AI success rate" / response-latency ms — those need time-series
  aggregation this app doesn't track yet. Don't fabricate those numbers if
  building the charts later; add real instrumentation first.

Section 5 (animation implementation order) is still pending — the tokens/
layout above are the "leaner" half; the motion layer hasn't been added yet.

## 1. Principles

- **Calm, not flashy.** The buyer is a clinic/salon owner checking if their
  AI receptionist is working. This is an operations tool, not a marketing
  site — motion should reassure and orient, never perform.
- **Lean by default.** Reach for CSS before JS, and a 2kb library before a
  30kb one. Every dependency added to `frontend/package.json` for animation
  has to earn its weight against a specific, named interaction — no "install
  Framer Motion and animate everything" pass.
- **Fast.** All transitions land in the 120–220ms range. Nothing animates
  past 300ms except the connection-status pulse (intentionally slow/ambient).
- **Respect `prefers-reduced-motion`.** Every animation layer below has a
  reduced-motion fallback (instant state change, no exceptions).

## 2. Visual language

### Color
Keep the existing CSS-variable token system in `globals.css`
(`--background`, `--card`, `--primary`, etc.) — it's the right foundation.
Change the values, not the structure:

- Base neutral: shift from pure gray to a very slightly warm gray
  (`oklch(0.99 0.002 95)` background family) — less clinical than shadcn's
  default stone-gray.
- One accent color: a muted teal/emerald (`oklch(0.6 0.09 165)` family),
  used *only* for: primary buttons, the active-nav indicator, "connected"
  status, and the outbound message bubble. Not decoration — it always means
  "this is the thing that's working / the thing to click."
- Status colors stay semantic and boring on purpose: green = connected/open,
  amber = needs attention, red = needs_human/failed, gray = closed/inactive.
  Don't get creative here — a clinic owner scanning the status page should
  never have to think about what a color means.

### Typography
Geist (already in the project) stays. Tighten the scale — current shadcn
defaults run large for a dense operations UI:
- Page heading: `text-xl font-semibold` (not `text-2xl`)
- Card title: `text-sm font-medium`
- Body/table text: `text-sm`
- Meta text (timestamps, masked keys): `text-xs text-muted-foreground`

### Density & elevation
This is the main "leaner" change:
- Drop the heavy bordered-card-everywhere pattern. Cards get a 1px border
  (`border-border/60`, not full opacity) and **no shadow at rest**. Shadow
  only appears on hover for genuinely interactive cards (conversation list
  rows), via `hover:shadow-sm transition-shadow`.
- Reduce card padding from the shadcn default (`p-6`) to `p-4` for list
  items, keep `p-6` only for form cards (settings, upload).
- Sidebar nav goes from `w-60` to `w-56`, and nav items lose their
  background-fill active state in favor of a thin animated indicator (see
  §3.1) — less "boxy," more editorial.

## 3. Animation system

Three layers, in order of preference — reach for the first one that solves
the problem.

### Layer 1 — CSS transitions (0kb, use everywhere)
Every interactive element gets a transition on `color`, `background-color`,
`border-color`, `transform`, and `box-shadow` via Tailwind's `transition-*`
utilities. This covers: button hover/press (`active:scale-[0.98]`), input
focus rings, link underlines, nav item color change. No library needed —
this is 90% of the "polish" perception for 0 bytes.

### Layer 2 — `tw-animate-css` (already installed, ~3kb)
Already pulled in by shadcn for Radix primitives (dialog, dropdown, select,
sonner toast) — their enter/exit animations come from this. Nothing to add;
just tune durations in each component's `data-[state=...]` classes if the
defaults feel sluggish. This layer owns: dialogs, dropdowns, toasts,
tooltips — anything Radix-driven.

### Layer 3 — `@formkit/auto-animate` (~2kb, add this)
For list animations: conversations list, documents list, messages in a
thread. Zero-config — attach a ref to the parent, children animate in/out/
reorder automatically. This is the leanest possible answer to "the list
should feel alive when items are added/removed," and it's the one new
dependency this doc asks for.

```bash
npm install @formkit/auto-animate
```

```tsx
import { useAutoAnimate } from "@formkit/auto-animate/react";
const [listRef] = useAutoAnimate();
// <div ref={listRef}> ...map over conversations... </div>
```

### What NOT to add yet
No Framer Motion / `motion` package for v1. Page-level route transitions and
orchestrated multi-element choreography are real "nice to have"s, but they're
a 30kb+ dependency for something Layers 1–3 don't need. Revisit only if a
specific moment (e.g. a first-run onboarding flow) genuinely needs
choreographed sequencing that auto-animate can't express.

## 4. Specific animation specs

| Moment | Treatment |
|---|---|
| Nav active item | 2px accent-color indicator slides between items via `transform: translateY()` on a shared absolutely-positioned element, 180ms ease-out. Replaces the current bg-fill active state. |
| Button press | `active:scale-[0.98] transition-transform duration-100` |
| Card hover (conversation row) | `hover:shadow-sm hover:border-border transition-all duration-150` |
| Toast (sonner) | Already handled — slide+fade from `tw-animate-css`, no change needed |
| Conversation list add/remove | `auto-animate` default (250ms, both layout and opacity) |
| Message bubble enter (new inbound/outbound) | `auto-animate` on the message list container |
| Connection status dot | Slow ambient pulse only when `connected`: `animate-pulse` at 2s duration on a 6px dot, not the whole card |
| Status badge change (e.g. open → needs_human) | Brief background-color flash via CSS transition (300ms), not a bounce/shake — this is a serious state change, not a celebration |
| Page load / route change | No custom transition — instant, Next.js's default. A loading skeleton (see below) covers perceived latency instead |
| Loading states | Replace all bare "Loading..." text with skeleton rectangles (`bg-muted animate-pulse rounded`) shaped like the content that's coming, matching each card's real layout |

## 5. Implementation order

1. Update `globals.css` color tokens (§2 Color) — 1 file, immediate visual
   shift, zero risk.
2. Tighten typography + density across existing pages (§2 Typography/
   Density) — mechanical pass through the 6 dashboard pages already built.
3. Nav active-indicator animation (§4 row 1) — one component,
   `dashboard/layout.tsx`.
4. Install `auto-animate`, wire into conversations list, documents list,
   message thread (§3 Layer 3) — 3 small edits.
5. Replace "Loading..." strings with skeleton components (§4 last row).
6. Status badge transition + connection-status pulse dot (§4).

Steps 1–2 alone will make the app feel meaningfully leaner even before any
animation work lands — do those first if this gets split across sessions.

## 6. Accessibility

Wrap `auto-animate` usage and any custom keyframe animation with a check
against `prefers-reduced-motion` (auto-animate respects this automatically;
for manual CSS animations, gate with the `motion-safe:` / `motion-reduce:`
Tailwind variants rather than a JS media query check).
