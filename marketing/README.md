# RISKON Marketing Site

A standalone React + Tailwind + Motion (Framer Motion) site, two pages:

- **`/`** — the landing page (product pitch, workflow, why-different, honest today-vs-future section)
- **`/future-vision`** — a long-form editorial page on where RISKON is headed and why

Separate on purpose from `frontend/` (the actual product demo, a single static HTML file with no
build step) — this is public-facing marketing copy, and keeping it apart means it can never affect
the tested, deployed demo app.

## Running it

```bash
npm install
npm run dev      # dev server with hot reload
npm run build    # production build -> dist/
npm run preview  # serve the production build locally
```

## Before this goes live

- Every CTA ("RISKON V0") links straight to the live deployed prototype — one URL, defined once in
  `src/constants.js` (`PROTOTYPE_URL`). Update it there if the deployment URL ever changes.
- Nothing here talks to RISKON's backend or database — it's pure static marketing copy, safe to deploy
  anywhere (Vercel, Netlify, a static Railway service, or as static files behind any web server).
- Where it should actually live relative to the demo app (same domain under a path, a separate
  subdomain, fully separate deployment) is a decision for you — this build doesn't assume one.
- **Routing needs an SPA fallback.** This uses React Router with clean URLs (`/future-vision`, not a
  `#` hash), which means the host must rewrite every path to `index.html` so a direct link or a
  refresh on `/future-vision` doesn't 404. A `public/_redirects` (Netlify) and `vercel.json` (Vercel)
  are already included; a different host will need the equivalent rule.
