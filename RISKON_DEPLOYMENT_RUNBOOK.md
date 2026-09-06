# RISKON Deployment Runbook

A practical, step-by-step manual for taking RISKON from "runs on my computer" to "a real link I can send a
client." Written after actually inspecting the current codebase (not assumed) and making the small set of
code changes that inspection showed were genuinely needed — see the changelog at the very bottom.

**One correction up front:** several requests referred to a demo company called "Apex Industrial
Manufacturing." No such company exists in this codebase. The synthetic company actually built into RISKON
is **Rex Industrial Manufacturing** (three plants: Rex North, Rex Central, Rex South). This document uses
the real name throughout.

---

## WHAT I SHOULD DO RIGHT NOW

If you do nothing else, do these 8 things, in this order, to get a real link you can send someone:

1. **Get a Claude API key** from [console.anthropic.com](https://console.anthropic.com/) (a few minutes,
   needs a payment method on file). You can start the steps below before it arrives — the app works and
   demos fine without it, just with AI analysis honestly disabled.
2. **Create a GitHub account/repo** if you don't have one, and push this project to it (Phase 2 below —
   5 commands, none of which touch your `.env`).
3. **Create a Railway account** at [railway.app](https://railway.app/) and connect it to that GitHub repo
   (Phase 5 — this is the one service that runs the whole app; there's no separate "frontend host" needed,
   see [Section 3](#3-recommended-architecture-and-why) for why).
4. **Add a persistent Volume** in Railway mounted at `/data`, and set `DATABASE_PATH=/data/riskon.db`
   (Phase 3 — five minutes, and it's the one step that's easy to forget and the most important not to).
5. **Set your environment variables** in Railway's dashboard: at minimum `ANTHROPIC_API_KEY` (once you have
   it), `DATABASE_PATH`, and a `DEMO_ACCESS_USERNAME`/`DEMO_ACCESS_PASSWORD` pair so the link isn't wide
   open to the entire internet (Phase 4 and Phase 9).
6. **Deploy** — Railway does this automatically once connected; watch the build log, then open the URL it
   gives you and confirm `https://<your-app>.up.railway.app/api/health` returns `"status":"ok"` (Phase 5).
7. **Click through it yourself first**, end to end, exactly like a client would (Phase 11) — this catches
   90% of embarrassing surprises before a client ever sees them.
8. **Send the link + the demo username/password** to your client (Phase 14).

Everything past this point in the document is the detailed version of these 8 steps, plus everything you
asked to have covered.

---

## 1. What I actually found when I inspected the project

RISKON today is **one Python web application** (built with FastAPI) that does two jobs at once: it serves
the app's single HTML/JavaScript file (the whole "frontend" is one file, no React/Vue/build step), and it
answers the handful of API calls that file makes for real data and AI analysis. Behind it sits **one SQLite
database file** — not a hosted database server, an actual file on disk — that already holds a complete,
realistic, entirely made-up dataset for Rex Industrial Manufacturing (100 incidents, 3 facilities, 30
employees, and so on).

This matters enormously for the deployment decision in Section 3: **there is no separate frontend to
deploy.** Deploying the backend deploys the whole product.

### CURRENTLY WORKING (verified by actually running it)

- Every screen: Dashboard, Incident Reporting, AI Investigation, Corrective Actions, Risk Register, Risk
  Intelligence, Continuous Learning, Executive Dashboard, Management Intelligence, Audit Trail, and the
  new Sign-Up page.
- The backend server, real database reads/writes, and a real (server-side-only) connection to Claude's API
  — the "Generate AI Analysis" button genuinely calls Claude, validates what comes back, and saves it.
- Submitting a new incident, approving/rejecting an AI analysis, marking a corrective action complete,
  giving feedback on a Continuous Learning recommendation, and signing up a profile — all real database
  writes when the server is running.
- A full automated test suite (42 tests) covering the backend, including what happens when Claude is
  unreachable, misconfigured, or returns something unexpected.
- The `/api/health` endpoint, which reports real database connectivity and whether AI is turned on.

### PARTIALLY WORKING (needs configuration, not code)

- **Claude AI analysis** — the code path is complete and was tested up to and including a real, correctly-
  rejected network call to Anthropic's servers with a placeholder key. Nobody has yet added a real, paid key
  and watched a genuine successful answer come back. That's a configuration step (Phase 7), not missing code.
- **A public, protected URL** — the app runs fine on `localhost`; making it reachable from the internet, and
  putting a simple password in front of it, are the subject of this whole document.

### MOCK / DEMO (by design, and worth knowing which is which)

- The entire company, all 100 incidents, all employees — synthetic, generated by a program, not real.
- 5 specific sample incidents show a full "AI investigation" that was **hand-written to look like AI
  output**, not produced by actually calling Claude. Every other incident goes through the real, live path.
- The "Risk Intelligence" and "Continuous Learning" pattern-detection screens are **real arithmetic on real
  data**, not machine learning — deliberately so, for transparency.
- The "Viewing as (demo)" role switcher and the new Sign-Up page are both identity **display** conveniences,
  not real login/security.

### MISSING (genuinely absent, not just unconfigured)

- Real user accounts with passwords, sessions, or password reset.
- A hosted, managed database (it's a file, today).
- Any monitoring/alerting service.
- A custom domain (you own none yet, unless you already do).
- Rate limiting on the API (nothing currently stops one browser tab from calling `/api/incidents/.../analyze`
  in a tight loop and running up a real Claude bill).

### PRODUCTION RISKS (things that could genuinely break or embarrass you if ignored)

1. **The database is a plain file.** Most hosting platforms give your app a *fresh, empty* disk on every
   deploy unless you explicitly attach persistent storage. Skip that step and your demo data — and anything
   a client types in — vanishes on the next deploy or restart. This is the single most important thing in
   this whole document. Covered in depth in Phase 3.
2. **No password in front of the app at all** means anyone who guesses or finds the URL can poke at it,
   including clicking "Generate AI Analysis" and running up your Claude bill. A lightweight fix for this
   (a single shared demo password) is built and ready — Phase 9.
3. **Nothing stops runaway Claude usage.** One person clicking a button in a loop, or a bot scanning the
   internet, could generate real charges. There's no hard spending cap in the code; Anthropic's own console
   lets you set one, and you should (Phase 7.6).
4. **Two old, unused data-generator scripts are still sitting in the project** from an earlier stage of
   building this. They still work, but running them by mistake would quietly regenerate the entire database
   with a different (though still fake) dataset. Left alone, they're harmless — just don't run
   `scripts/generate_synthetic_data.py` or `scripts/build_frontend_data.py` thinking they're the current ones.

---

## 2. Deployment-readiness changes made during this pass

Per your instruction to make necessary changes without unnecessarily rebuilding anything, five small,
additive things were built and tested (all 42 backend tests pass, including 11 new ones covering exactly
these changes):

| Change | Why | File(s) |
|---|---|---|
| The server now honors the standard `PORT` environment variable (falling back to `RISKON_PORT`, then 8743) | Every mainstream hosting platform assigns your app a port at runtime through this exact variable | `backend/config.py`, `backend/main.py` |
| A one-time "seed the database if the target location is empty" step on startup | Makes a fresh persistent volume usable immediately on first deploy, with zero manual server-console steps, while never touching a volume that already has real data on it | `backend/db.py` |
| An optional, shared-password gate (off unless you turn it on) protecting the whole app | The simplest possible way to stop a public URL from being wide open before real accounts exist | `backend/middleware.py`, `backend/config.py` |
| A `Dockerfile`, `.dockerignore`, `Procfile`, and `.python-version` | Gives every hosting platform a clear, tested, unambiguous way to build and start the app, whether it uses Docker or auto-detects Python | repo root |
| `database/riskon.db` is meant to be committed to git as the starting seed | It's 600 KB of entirely synthetic data, not a secret — see Phase 1 for the reasoning | (decision, not a code change) |

Nothing about how any existing screen looks or behaves changed. All of this was tested locally, including
simulating a completely empty, freshly-provisioned server and confirming it comes up correctly with the
seed data already loaded.

---

## 3. Recommended architecture, and why

```
                                Client / Prospect's Browser
                                          │
                                          ▼
                              Custom domain (optional, Phase 12)
                                          │
                                          ▼
                    ┌─────────────────────────────────────────┐
                    │              RAILWAY (or similar)         │
                    │  ONE service running the RISKON backend:  │
                    │   • serves the app's one HTML/JS file      │
                    │   • answers every /api/* request            │
                    │   • the shared-password demo gate            │
                    └───────────────────┬─────────────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                  ▼
              ┌──────────────────┐               ┌──────────────────┐
              │  Persistent       │               │   Claude API      │
              │  Volume — the     │               │   (Anthropic)     │
              │  SQLite database  │               │  server-to-server │
              │  file             │               │  only, key never  │
              └──────────────────┘               │  reaches the      │
                                                   │  browser          │
                                                   └──────────────────┘
```

**Why one service, not a separate frontend host:** the standard advice ("static frontend on Vercel, API on
Railway") solves a problem RISKON doesn't have. That pattern exists for apps with a real frontend build step
(React, Next.js, etc.) that benefits from a specialized static-hosting CDN. RISKON's entire frontend is one
already-built HTML file that the backend already serves directly, and every fetch in it uses a relative
address like `/api/health` rather than a hardcoded server address — meaning it already assumes it's being
served from the same place as its API. Splitting them across two platforms would mean: two things to deploy
and keep in sync, a second URL to manage, and a new CORS (cross-origin) configuration problem to solve —
for an app that has zero technical need for any of that today.

**Why Railway specifically, over Render or Fly.io:** all three are reasonable, and the honest answer is
"any of them would work fine" — but for this specific project, right now:

- **Render's** free tier does not support the persistent storage this app needs for its database, so you'd
  need at least its paid Starter tier (about $7/month) from day one regardless.
- **Fly.io** no longer offers an ongoing free tier to new accounts (only a one-time trial credit as of this
  writing) [[srvrlss.io]](https://www.srvrlss.io/provider/railway/) [[saaspricepulse.com]](https://www.saaspricepulse.com/blog/flyio-free-tier-2026), and its normal workflow leans on installing a separate command-line tool and writing
  Fly-specific configuration — more setup steps for the same result.
- **Railway** connects directly to a GitHub repo through its web dashboard (no separate CLI required),
  supports persistent volumes on its cheapest paid tier, and that tier costs about $5/month *of included
  usage* rather than a flat fee — meaning a small demo app often runs close to that $5 alone
  [[Railway Docs]](https://docs.railway.com/pricing/plans) [[costbench.com]](https://costbench.com/software/developer-tools/railway/).

None of this is a strong technical requirement — it's "least friction to a working, persistent, public URL
today." If you already have a Render or Fly.io account you like, the Dockerfile built during this pass
works unmodified on either; Phase 5 notes the small differences.

### Alternative architecture (and when it would actually make sense)

**Split hosting** — a static-hosting service (Vercel/Netlify/Cloudflare Pages) for the frontend file, and
Railway/Render for the backend API. This becomes the *right* choice the day RISKON's frontend is rewritten
as a proper framework app (React/Next.js/etc.) with its own build pipeline and its own reasons to want a
specialized CDN — think faster global page loads for a much heavier frontend. At today's scale (one ~800 KB
HTML file), that architecture would add real complexity (a second deploy, CORS configuration, two places
things can go wrong) for a performance benefit nobody would notice on a demo with a handful of concurrent
users. Keep this in your back pocket for later, not now.

**Database alternative — hosted Postgres (Supabase/Neon/Railway Postgres) instead of SQLite-on-a-volume:**
a completely reasonable *future* upgrade (better for many simultaneous writers, built-in backups, a real
admin UI), but not required to go live now, and switching would mean rewriting every database query in the
backend (they're currently plain, portable SQL, but written for SQLite's specific quirks) — real, avoidable
work for a problem (many concurrent writers) a client demo doesn't yet have. Section 8 covers exactly what
that migration would involve when the time comes.

---

## 4. The deployment plan, in the actual correct order for this project

```
STEP 1   Decide what's committed to git (the database file included) and initialize the repository
STEP 2   Push to GitHub
STEP 3   Create a Railway project and connect the GitHub repo
STEP 4   Attach a persistent Volume, set DATABASE_PATH to point into it
STEP 5   Set every environment variable Railway needs (Section 6's table)
STEP 6   Deploy — Railway builds and starts the one service automatically
STEP 7   Confirm /api/health looks right on the live URL
STEP 8   Add your real Claude API key as an environment variable and re-check /api/health
STEP 9   Turn on the shared demo password (DEMO_ACCESS_USERNAME / DEMO_ACCESS_PASSWORD)
STEP 10  Click through the entire app yourself on the live URL, exactly like a client would
STEP 11  (Optional) Point a custom domain at the Railway service
STEP 12  Send the link + demo password to your client
```

Notice there is no separate "deploy backend" and "deploy frontend" step, and no separate "connect frontend
to backend" step — both of those are already true the moment Step 6 finishes, because they're the same
service. That's the biggest way this plan differs from a generic template.

---

## Phase 1 — Prepare

**Action:** Decide what belongs in git, then make sure nothing that shouldn't be there can be.

**Where:** Your local project folder, in a terminal.

**What to check:**
- `.gitignore` already exists and already excludes `.env`, `.env.local`, Python cache folders, and common
  editor/OS clutter. Open it once and confirm it looks like this (it does, as of this writing):
  ```
  .env
  .env.local
  .env.*.local
  .env.production
  .env.development
  __pycache__/
  *.pyc
  .pytest_cache/
  .venv/
  venv/
  node_modules/
  *.log
  .DS_Store
  ```
- **`database/riskon.db` should be committed, not ignored.** This feels counter-intuitive (a database file
  in git!) but it's the right call here specifically because it contains zero real information — it's 100%
  synthetic Rex Industrial Manufacturing data, generated by a script also in this repo. Committing it means
  a fresh deployment has real, working demo data the instant it starts, with no extra manual step. If this
  file ever holds real client data in the future, that decision must be revisited before that day — flagged
  here so it isn't forgotten.
- `.env` and `.env.example` — see Phase 4 for the full variable list. `.env.example` should already exist
  with every variable name present and every value blank. `.env` should exist locally for your own testing
  and must never be committed (the `.gitignore` entry above already prevents this).

**What result you should see:** running `git status` (after Phase 2's `git init`) should list `.env` nowhere
— not staged, not untracked-but-visible, not anywhere.

**How to verify success:**
```bash
git init
git add .
git status
```
Read the output. `.env` must not appear. If it does, your `.gitignore` isn't being picked up (check you're
running this from the project's root folder) — fix that before continuing.

**Common errors:** accidentally running this from inside a subfolder (`backend/`, `frontend/`) instead of
the project root — `git init` there would create a second, wrong repository nested inside the real one. Run
`pwd` first and confirm you're at the top level.

---

## Phase 2 — GitHub

**Action:** Push the local repository to GitHub.

**Where:** [github.com](https://github.com/) (create a free account if you don't have one) and your
terminal.

**What to do:**
1. On GitHub, create a new **empty** repository (don't let it auto-add a README/`.gitignore` — you already
   have one). Name it `riskon` or similar. Choose Private unless you have a specific reason to make it
   public.
2. Back in your terminal, at the project root:
   ```bash
   git add .
   git commit -m "Initial commit: RISKON prototype ready for deployment"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

**Branching for a PoC:** you don't need a branching strategy yet. Commit to `main` directly while it's just
you. The moment a second person touches this code, adopt the simplest possible rule — a short-lived branch
per change, merged back into `main` — nothing fancier than that is justified at this stage.

**What result you should see:** refreshing the GitHub repo page shows all your files, and — importantly —
does **not** show a `.env` file anywhere in the listing.

**How to verify success:** open the repo on GitHub's website and use its search/file browser to confirm
`.env` isn't there. If you ever see it: immediately treat any key that was in it as compromised (rotate it
at [console.anthropic.com](https://console.anthropic.com/)), then remove it from git history — a bigger
topic than this document covers, but the short version is `git filter-repo` or GitHub's own
"remove sensitive data" guide, followed by force-pushing the cleaned history.

**Common errors:** "remote origin already exists" — you already ran `git remote add` once; use
`git remote set-url origin <url>` instead. "Authentication failed" pushing to GitHub — GitHub no longer
accepts your account password for this; you need a
[Personal Access Token](https://github.com/settings/tokens) or to have set up SSH keys, used as your
password when prompted.

---

## Phase 3 — Database

**Action:** Make sure the database survives deploys and restarts.

**Where:** Railway's dashboard (once your project exists — see Phase 5), plus the code changes already made
during this pass.

**What RISKON currently uses:** SQLite — a single file (`database/riskon.db`), not a separate database
server. It's real, it's fully relational (23+ tables with real foreign keys), and it's the same file every
part of this project already reads and writes locally.

**Can it be deployed directly? Yes, with one condition.** The file must live somewhere that survives a
redeploy. Most platforms wipe the disk your app runs on every time you deploy new code — anything your app
saved to a plain local path disappears. The fix is a **persistent volume**: extra, durable disk space the
platform keeps around across deploys, that you mount at a specific folder path.

**Exact steps on Railway:**
1. In your Railway project, open your service → the **Volumes** tab → **New Volume**.
2. Mount it at `/data` (any path works; `/data` is the clearest choice).
3. Set the environment variable `DATABASE_PATH=/data/riskon.db` (Phase 4).
4. Deploy. On first boot, the code added during this pass notices `/data/riskon.db` doesn't exist yet, and
   automatically copies the seed database (the one committed to git in Phase 1) into place — you do not
   need to SSH in or run any command by hand. Every real thing a client does afterward — new incidents,
   sign-ups, AI analyses, approvals — is saved on that volume and survives every future deploy.

**Are migrations required?** Not in the traditional sense — there's no migration tool, but the app itself
safely and automatically adds the few extra tables it needs (for AI analyses and sign-up profiles) on every
startup, without ever touching or resetting the tables that already have data in them. This has been tested
against both a brand-new empty volume and a volume with existing data.

**Is seed data required?** Yes, and it's already handled — see the auto-seed step above.

**Should the "Apex" synthetic data be included?** As covered earlier, that name doesn't correspond to
anything in this codebase. The real Rex Industrial Manufacturing dataset already committed to git *is* your
demo data, and it's comprehensive enough for a full walkthrough (Phase 10 covers exactly what it supports).

**How to protect production data:** the persistent volume is private to your Railway project by default —
nobody can reach it except through your app's own API. The main protection to add is the demo-access
password (Phase 9), so random internet traffic can't reach the API and start writing to it at all.

**Row-Level Security / real per-client data isolation:** not applicable yet — there is exactly one dataset
(Rex Industrial Manufacturing) and no concept of separate client tenants in the database today. This becomes
relevant only once you have multiple real clients with data that must never mix, which is a future-phase
concern, not a launch blocker for a single-tenant demo.

**Backups:** Railway volumes are durable but you should still take your own periodic backup — the simplest
approach for a file this small (under 1 MB) is a scheduled task that downloads a copy via a small admin
script, or manually pulling a copy every so often while this is still low-stakes. A proper automated backup
policy is a Phase-2-of-the-business-not-Phase-2-of-this-document concern; don't over-invest here yet.

---

## Phase 4 — Environment Variables

**The complete list this application actually uses** (verified against `backend/config.py` — nothing here
is a guess):

| Variable | Used by | Required? | Secret? | Where to set it |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | Claude AI analysis | Only if you want real AI analysis to work | **Yes** | Local `.env`; Railway → your service → Variables |
| `ANTHROPIC_MODEL` | Which Claude model to call | No (defaults to `claude-sonnet-5`) | No | Same as above, if you want to override it |
| `ANTHROPIC_TIMEOUT_SECONDS` | How long to wait for Claude | No (defaults to 30) | No | Same |
| `ANTHROPIC_MAX_TOKENS` | Response length cap | No (defaults to 1536) | No | Same |
| `DATABASE_PATH` | Where the SQLite file lives | **Yes, in production** (so it points at the volume) | No | Railway → Variables, e.g. `/data/riskon.db` |
| `RISKON_HOST` | What network interface to bind | No (defaults to `0.0.0.0`, already correct for hosting) | No | Rarely needed |
| `PORT` | What port to listen on | Set automatically by Railway/Render/Fly — don't set it yourself | No | Provided by the platform |
| `CORS_ORIGINS` | Which origins may call the API | No (defaults to allow all — fine, since the frontend is served from the same place) | No | Only if you ever split hosting (see Section 3) |
| `DEMO_ACCESS_USERNAME` | The shared demo login's username | Strongly recommended before sharing the link publicly | No (a username, not a password) | Railway → Variables |
| `DEMO_ACCESS_PASSWORD` | The shared demo login's password | Strongly recommended | **Yes** | Railway → Variables |
| `LOG_LEVEL` | How chatty the server's logs are | No (defaults to `INFO`) | No | Rarely needed |
| `RISKON_ENV` | Cosmetic label shown in `/api/health` | No | No | Optional |

Notice what's **not** in this list: no `DATABASE_URL`, `SUPABASE_URL`, or any Supabase key — this app
doesn't use Supabase or Postgres today, so those variables would do nothing. No
`NEXT_PUBLIC_API_URL` either — there's no separate frontend build that needs to be told where the API lives,
because there is no separate API address; the frontend calls `/api/...` on whatever address it's already
loaded from.

**Local setup:**
```bash
cp .env.example .env
# open .env and fill in ANTHROPIC_API_KEY when you have it; everything else has a working default
```

---

## Phase 5 — Backend (and, at the same time, the whole app)

**Action:** Deploy the one Railway service that runs everything.

**Where:** [railway.app](https://railway.app/)

**Steps:**
1. Sign in to Railway with your GitHub account.
2. **New Project → Deploy from GitHub repo** → pick your `riskon` repository.
3. Railway will detect the committed `Dockerfile` and build from it automatically. (If it instead offers to
   auto-detect a Python app via Nixpacks, that also works — just make sure the **Start Command** it uses is
   `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, which matches the committed `Procfile`.)
4. **Runtime:** Python 3.11 (pinned in the committed `.python-version` file).
5. **Build command:** none needed manually — the Dockerfile's `pip install -r backend/requirements.txt`
   handles it, or Nixpacks does the equivalent automatically if it detects the requirements file.
6. **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` (already correct in both the
   Dockerfile and the Procfile — nothing to type unless Railway asks).
7. **Port:** don't hardcode one. Railway injects `PORT`, and the app already reads it (Phase-1-of-this-pass
   code change) — this was tested locally by simulating a platform-assigned port and confirming the app
   bound to it correctly.
8. Attach the persistent Volume from Phase 3, and set the environment variables from Phase 4.
9. **Health check:** point Railway's health check at `/api/health` — it's deliberately left un-gated even
   after you turn on the demo password (Phase 9), specifically so automated health checks like this one
   keep working.
10. Deploy. Watch the build log for errors (the most common one at this stage is a missing environment
    variable causing a clear, logged startup message — never a silent failure).

**What result you should see:** Railway gives you a URL like `https://riskon-production.up.railway.app`.
Opening it in a browser shows the exact same RISKON app you've been running locally.

**How to verify success:**
```bash
curl https://<your-railway-url>/api/health
```
should return something like:
```json
{"status":"ok","database":{"ok":true,"incident_count":100},"ai_configured":false,...}
```

**Common errors:**
- `database_not_ready` in the health response → the Volume isn't attached yet, or `DATABASE_PATH` doesn't
  point at it. Recheck Phase 3.
- App builds but crashes immediately → check the log for a plain Python traceback; the most likely cause at
  this stage is a typo in an environment variable name.
- **If Render is what you chose instead:** the same Dockerfile works — create a "Web Service," point it at
  the repo, Render detects the Dockerfile automatically, and you'd add a **Persistent Disk** (Render's name
  for the same concept as Railway's Volume) under the service's Disks tab, on any paid instance type (the
  free tier doesn't support disks at all).

---

## Phase 6 — Frontend

There is no separate frontend deployment step — see Section 3 for why. If you ever change
`frontend/app.template.html`, rebuild the single shipped file before your next deploy:
```bash
python3 scripts/build_frontend.py
git add frontend/riskon.html
git commit -m "Rebuild frontend"
git push
```
Railway redeploys automatically on every push to `main`.

---

## Phase 7 — Claude API

1. **Where the key goes locally:** your `.env` file, as `ANTHROPIC_API_KEY=sk-ant-...`. Never in any source
   file.
2. **Where it goes in production:** Railway's Variables tab for your service — never in git, never visible
   in any file in the repo.
3. **How the backend accesses it:** one file, `backend/services/ai/claude_service.py`, reads it via
   `backend/config.py` and uses it to construct the Anthropic client. No other file touches it, and it is
   never included in any API response sent back to a browser.
4. **How to test that it works:** once the key is set and the app has redeployed,
   ```bash
   curl -X POST https://<your-railway-url>/api/incidents/INC-0001/analyze
   ```
   A successful response returns a structured JSON analysis. This is the one thing that could not be
   verified before this document was written, since no real key was available — everything up to and
   including a real network call with a placeholder key was tested and behaved correctly (a clean, safe
   error, not a crash).
5. **How Claude API failures are handled:** already built and tested — a timeout, a rate limit, an
   unreachable network, or a malformed response all produce a calm, specific error message to whoever
   clicked the button, and nothing is ever invented to paper over a failure.
6. **How to monitor usage/cost:** Anthropic's own console
   ([console.anthropic.com](https://console.anthropic.com/) → Usage/Billing) shows real-time spend. Set a
   spending limit there — this is the single most important cost-control step, since nothing in RISKON's
   own code currently caps how many times the analyze button can be called. The server also logs every
   attempt (success or failure, with timing) to its own logs, viewable in Railway's Logs tab, without ever
   logging the key itself.

---

## Phase 8 — Connect Everything

Because the frontend and backend are the same deployed service, this phase is mostly already done the
moment Phase 5 finishes. What's worth explicitly checking:

- **Production API address:** none to configure — it's always "wherever this page was loaded from."
- **CORS:** irrelevant for normal use (same-origin); only matters if you adopt the split-hosting alternative
  from Section 3 later, in which case you'd set `CORS_ORIGINS` to your frontend's exact address.
- **HTTPS:** Railway (and Render, and Fly.io) provision this automatically for their own subdomains and for
  any custom domain you attach — nothing to configure by hand.
- **Error handling across the connection:** already built — every API error comes back as a small,
  consistent `{"error": ..., "message": ...}` object, never a raw stack trace, and the frontend already
  knows how to show a plain-language message for each one.

---

## Phase 9 — Authentication

**What exists today:** no login, no password, no sessions, no protected routes at the network level. The
"Viewing as (demo)" role switcher and the Sign-Up page are both identity *conveniences* — real features, but
not security. Anyone with the URL can do anything the UI allows.

**What to do before showing this to an external client:** turn on the shared-password gate built during this
pass. In Railway's Variables:
```
DEMO_ACCESS_USERNAME=your-choice-of-username
DEMO_ACCESS_PASSWORD=a-real-password-you-choose
```
Once both are set (and the app redeploys), every page and every API request requires that single username
and password via the browser's own built-in login prompt — except `/api/health`, left open on purpose for
platform health checks. This is **Option A** from your question:

- **Option A — one shared demo account (recommended right now):** simplest possible thing that actually
  works, took under an hour to build and verify, and is completely adequate for "a handful of trusted
  prospects click a link I sent them."
- **Option B — individual client accounts:** the right long-term answer, but real work — actual user
  records, real password handling, session management, and a decision about whether different clients
  should ever see different data. Not justified yet when there's exactly one demo dataset and a small,
  known list of people you're sending the link to.
- **Option C — both, eventually:** start with A today; layer B in once you have real, distinct clients who
  need their own logins or their own data. Nothing about Option A blocks building Option B later — the
  demo-gate middleware is a thin layer sitting in front of everything, independent of any future real
  accounts system.

**Recommendation: Option A, now.**

---

## Phase 10 — Demo Environment

**Design:** RISKON doesn't need a separate "demo mode" toggle, because there is currently no real client
data anywhere in it to accidentally expose — the *entire* deployed app already is the safe demo
environment. The thing to get right isn't data isolation (there's nothing private to isolate yet); it's
making sure a first-time visitor understands what they're looking at without you standing next to them.

**What a client can already explore, unassisted, using the real Rex Industrial Manufacturing dataset:**
- **Dashboard** — headline numbers and recent activity across all three plants.
- **Facilities** — implicitly, via the facility switcher in the sidebar (there isn't a dedicated
  "Facilities" page, but every screen can be filtered to one of the three plants).
- **Incidents** — the full Incident Reporting screen, including submitting a brand-new one.
- **Investigations & AI analysis** — pick any of the ~100 real incidents, click "Generate AI Analysis" (once
  your key is live), and see a genuine Claude response.
- **Recommendations & corrective actions** — approve/reject an AI analysis, watch a real follow-up task get
  created, and mark it complete.
- **Risk Register & Risk Intelligence** — the risk-scoring grid and the pattern-detection screen.
- **Continuous Learning** — including the one fully-interactive "try it yourself" feedback example.
- **Management Intelligence & Executive Dashboard** — the leadership-level summaries.

**Not currently present as named features, worth setting expectations about if a client specifically asks:**
a literal "Risk Graph" (network-diagram) visualization and a literal "Global Risk Map" — RISKON shows
relationships as clear step-by-step chains (e.g., Incident → Recommendation → Decision → Outcome) rather
than an interactive node-and-edge graph, and shows facility comparisons as data, not a geographic map. If
either of those specific visual formats matters to a prospect, that's a scoped follow-up feature, not
something to imply already exists.

**The one thing worth adding before a client sees it:** a small, honest label somewhere visible (the login
screen or a footer note) along the lines of *"Demo environment — Rex Industrial Manufacturing is a
fictional company; all data is synthetic."* This isn't required for the app to function, but it's the kind
of small trust-building detail that makes a demo feel more professional, not less — nobody should wonder for
even a second whether they're looking at a real company's private safety data.

---

## Phase 11 — Testing

**Test the whole chain for real, in this order, on the live URL, before sending it to anyone:**

1. Load the URL → confirm the demo-password prompt appears (Phase 9) → log in.
2. Dashboard loads with real numbers (not zeros, not an error).
3. Submit a new test incident on Incident Reporting → confirm it appears in the list.
4. Open AI Investigation, pick that new incident, click "Generate AI Analysis" → confirm a real result comes
   back (or, if no key is set yet, confirm the honest "AI provider not configured" message appears — not a
   crash, not a fake result).
5. Approve it → confirm a corrective action appears on the Corrective Actions screen.
6. Mark that action complete.
7. Go to Continuous Learning → try the "Try It" feedback example.
8. Go to Risk Intelligence and the Executive Dashboard → confirm charts and numbers render.
9. Go to Audit Trail → confirm every action above shows up in the log.
10. Refresh the page entirely → confirm everything you just did is *still there* (this is the real test of
    whether the persistent volume from Phase 3 is actually working).
11. Open the same URL in an incognito/private window → confirm the password prompt appears again and the
    app still works cleanly for a "fresh" visitor.

If anything in this list fails, the fix is almost always one of: the Volume isn't attached (Phase 3), an
environment variable is missing (Phase 4), or the Claude key isn't set yet (Phase 7) — in that order of
likelihood.

---

## Phase 12 — Custom Domain

Not required to demo RISKON — the Railway-provided URL works today. When you're ready for something like
`www.riskon.ai` (checking availability is your first step; that specific domain may or may not be free):

1. Buy the domain from any registrar (Namecheap, Google Domains successor Squarespace Domains, Cloudflare
   Registrar — any of them work identically for this purpose).
2. In Railway, open your service → Settings → Networking → **Custom Domain** → enter your domain.
3. Railway gives you one or more DNS records to add (typically a `CNAME`) — go to your domain registrar's
   DNS settings and add exactly what Railway shows you.
4. Wait for DNS to propagate (usually minutes, occasionally up to a few hours) and for Railway to
   automatically issue an HTTPS certificate for it — no separate certificate step needed.
5. Redirects: decide once whether `riskon.ai` should redirect to `www.riskon.ai` or vice versa, and set that
   as the "primary" domain in Railway's settings; it handles the redirect for you.

---

## Phase 13 — Monitoring

**What to actually watch, at this stage, without overengineering it:**

- **Uptime/errors:** Railway's own dashboard shows CPU, memory, and request logs for free — for a PoC,
  glancing at this after a demo is enough. If you want a nudge without babysitting it, a free tier of
  [UptimeRobot](https://uptimerobot.com/) pinging `/api/health` every few minutes and emailing you on
  failure takes five minutes to set up.
- **Claude usage/cost:** Anthropic's own console (Phase 7.6) — check it after any demo session, and
  definitely set a spending cap there.
- **Application errors:** already logged to Railway's Logs tab by the backend's existing logging — no new
  tool needed to *see* errors, just a habit of checking after each demo.
- **What NOT to set up yet:** a dedicated error-tracking service (Sentry and similar), structured log
  aggregation, or uptime dashboards with paging/on-call — all genuinely useful later, all overkill for "a
  handful of demo sessions a week."

---

## Phase 14 — Client Launch

1. Confirm Phase 11's full test pass on the live URL, today, right before sending anything.
2. Write a one-line message: the URL, the demo username/password, and one sentence of context ("this is a
   working prototype using a fictional company's data — click around, try the AI Investigation screen").
3. Send it.
4. Watch Railway's logs and Anthropic's console during the first live session if you can, just in case.
5. Afterward, check Audit Trail on the live app — it's a genuine record of everything the client actually
   clicked, which is also a nice thing to skim before your next conversation with them.

---

## 5. GitHub setup summary

- **Commit:** all source code, `database/riskon.db` (synthetic seed data, not a secret),
  `frontend/riskon.html` (the pre-built app file), `.env.example`, this runbook and the other `.md` docs,
  the `Dockerfile`/`Procfile`/`.dockerignore`/`.python-version`.
- **Never commit:** `.env`, any file containing a real API key, `__pycache__/`, `.pytest_cache/`.
- **`.env` handling:** exists locally only, git-ignored, holds your real key during local development.
- **`.env.example` handling:** committed, every variable name present, every value blank — the "menu" of
  what needs to be configured wherever the app runs.
- **Branches:** just `main` for now (Phase 2); revisit only once more than one person is committing.

---

## 6. Production Readiness Checklist

**Code**
| Item | Status |
|---|---|
| App starts and serves pages | READY |
| Automated tests | READY — 42 passing |
| Error handling (no stack traces leaked) | READY |
| Type checking / linting as a CI gate | MISSING — none configured; not a blocker for a PoC demo |

**Backend**
| Item | Status |
|---|---|
| API working | READY |
| Database connected | READY (once a persistent volume is attached — Phase 3) |
| CORS | READY (not needed for the recommended single-service setup) |
| Authentication | NEEDS WORK — shared demo password built and ready to turn on (Phase 9); real per-user accounts are a future item |
| Logging | READY |
| Health endpoint | READY |

**AI**
| Item | Status |
|---|---|
| Claude API connected | READY (code); NEEDS WORK (a real key has never been tested against it) |
| API key secure | READY — server-only, never in git, never returned to a client |
| AI responses validated | READY |
| Failure handling | READY |
| Usage monitoring | NEEDS WORK — use Anthropic's own console; no spending cap set yet |

**Database**
| Item | Status |
|---|---|
| Production database | NEEDS WORK — works today, needs the persistent volume (Phase 3) before it's durable |
| Migrations | READY (automatic, additive-only) |
| Seed data | READY |
| Backups | MISSING — none automated yet; acceptable for now, flagged for later |
| Security | NEEDS WORK — protected by the demo gate (Phase 9), not by real per-user permissions |

**Frontend**
| Item | Status |
|---|---|
| Production build | READY — one file, already built |
| API connection | READY — relative addresses, works anywhere it's hosted |
| Loading states | READY |
| Error states | READY |
| Responsive design | PARTIAL — built and used as a desktop-oriented business app; not verified on small mobile screens |

**Security**
| Item | Status |
|---|---|
| Secrets protected | READY |
| `.env` ignored | READY |
| HTTPS | READY (automatic on Railway/Render/Fly) |
| Authentication | NEEDS WORK (see above) |
| Authorization | NEEDS WORK — role permissions exist in the UI but aren't enforced server-side yet |
| No exposed API keys | READY |

**Client Demo**
| Item | Status |
|---|---|
| Demo account | READY (Option A, Phase 9) |
| Synthetic data | READY |
| Reset capability | PARTIAL — re-running the two seed scripts resets everything, but there's no one-click "reset demo" button in the UI yet |
| Clear onboarding | NEEDS WORK — recommend the one-line disclaimer from Phase 10 |
| No private data | READY — there is no private data in the system at all today |

---

## 7. Performance & Cost

Realistic, PoC-level numbers, current as of this writing (pricing changes — verify before committing):

| Item | Free / $0 | Minimum paid | Comfortable professional |
|---|---|---|---|
| Hosting (Railway) | Not realistically usable for an always-on demo | ~$5/month (Hobby plan's included usage) [[Railway Docs]](https://docs.railway.com/pricing/plans) | $20/month (Pro plan, more resources/support) |
| Persistent volume | — | A few cents/month for 1 GB (~$0.15–0.25/GB) [[costbench.com]](https://costbench.com/software/developer-tools/railway/) | Same — this file is tiny |
| Claude API | Pay-as-you-go, no free tier | ~$0.01–0.02 per AI analysis at Sonnet 5 pricing ($2/$10 per million tokens in/out) — a few dollars covers dozens of demo analyses [[BenchLM.ai]](https://benchlm.ai/anthropic/api-pricing) | Set a $20–50/month cap in Anthropic's console as a safety net |
| Database | Included in hosting (it's a file) | Included | If you later move to hosted Postgres: Supabase/Neon free tiers exist, ~$25/month for their smallest paid tier |
| Domain | — | ~$10–15/year for a typical `.com`/`.ai` domain | Same |
| Monitoring | Free (UptimeRobot free tier, Railway's built-in dashboard) | Free | ~$10–30/month if you later add a dedicated error tracker |
| **Realistic total to start** | — | **~$6–8/month** plus a few dollars of AI usage per demo | **~$30–60/month** |

Optimized for "working, reliable, presentable, inexpensive" — not enterprise scale, exactly as asked.

---

## 8. Client-Safe Architecture

How the recommended setup prevents each of the following, at this stage:

- **Seeing API keys:** the key lives only in Railway's environment variables and the backend's memory; it's
  never included in any HTML, JavaScript, or API response sent to a browser.
- **Accessing other clients' data:** not yet applicable — there is one dataset, and it's synthetic. Real
  data isolation becomes a design task the day a second, distinct real client dataset needs to exist.
- **Modifying production configuration:** environment variables are only editable inside Railway's
  dashboard, which only you (or whoever you invite to the Railway project) can access.
- **Accessing admin functionality:** there is no separate "admin" surface today — every route is protected
  equally by the shared demo password.
- **Accessing private data:** none exists in the system yet.
- **Breaking the database:** the demo password gate is the main defense against a stranger even reaching the
  API; within the app itself, every input is validated before it's saved (this was already true before this
  deployment pass).
- **Abusing AI API usage:** the demo password gate is the practical stopgap today; the real fix (rate
  limiting inside the backend) is listed as a near-term follow-up in Section 1's Missing list, and a
  spending cap in Anthropic's console (Phase 7.6) is the safety net in the meantime.

---

## 9. Final recommended architecture

```
                              CLIENT / PROSPECT
                                     │
                                     ▼
                    (optional) www.your-domain.com
                                     │
                                     ▼
                       ┌─────────────────────────┐
                       │        RAILWAY            │
                       │  ONE FastAPI service:      │
                       │   • the RISKON app itself    │
                       │   • every /api/* route         │
                       │   • the shared demo-password     │
                       │     gate                            │
                       └───────────────┬───────────────────┘
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                                 ▼
              ┌──────────────────┐              ┌──────────────────┐
              │ Persistent Volume  │              │   Claude API       │
              │ (SQLite database   │              │   (Anthropic) —     │
              │  file — the real,   │              │   server-to-server,  │
              │  already-built       │              │   key never leaves    │
              │  Rex Industrial data) │              │   Railway              │
              └──────────────────┘              └──────────────────┘
```

No separate frontend host, no separate database server, no split repos — one service, one URL, one place to
look when something needs attention. This is the right amount of infrastructure for what RISKON is today.

---

## 10. The most important question, answered directly

> *"If I stop coding today and want to show RISKON to a potential client tomorrow, exactly what must I do
> before I send them the link?"*

1. Push the current code to GitHub (Phase 2 — five commands).
2. Deploy it to Railway with a persistent volume attached (Phases 3 and 5 — the volume is the one step you
   cannot skip).
3. Set `DEMO_ACCESS_USERNAME` and `DEMO_ACCESS_PASSWORD` so the link isn't wide open (Phase 9).
4. If you have a Claude key by then, add `ANTHROPIC_API_KEY` too (Phase 7) — if not, the app still works and
   demos fine, just with AI analysis honestly showing as not yet enabled instead of faking a result.
5. Click through the entire app yourself on the live URL, exactly as in Phase 11's checklist, once, start to
   finish.
6. Send the URL and the demo password. Nothing else is required to have a real, working, presentable demo.

Everything past that point — a custom domain, monitoring, real per-user accounts, moving off SQLite — makes
RISKON *better*, not *demoable*. Demoable is achievable with the six steps above.

---

## Changelog (this pass)

- `backend/config.py` — reads the standard `PORT` variable; added `demo_access_username`/
  `demo_access_password` settings.
- `backend/main.py` — mounted the new demo-access middleware; added a `python3 -m backend.main` convenience
  entrypoint; calls the new database auto-seed step on startup.
- `backend/db.py` — added `ensure_database_seeded()`.
- `backend/middleware.py` — new file, the shared-password gate.
- `backend/tests/test_demo_access.py`, `backend/tests/test_db_seeding.py` — new tests (11 total) covering
  both additions; full suite (42 tests) passing.
- `Dockerfile`, `.dockerignore`, `Procfile`, `.python-version` — new files, all tested locally (including
  simulating a platform-assigned port and a completely fresh, empty database volume).

No existing screen, route, or behavior was changed or removed.
