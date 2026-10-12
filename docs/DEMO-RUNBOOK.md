# Andon Assistant — Demo Runbook
**Audience:** Toyota group leader · **Running on:** Claude (Anthropic) · **Framing:** shop-floor troubleshooting
**App:** dashboard at http://localhost:3000, backend at http://localhost:8080

---

## 0. TL;DR timeline
1. **Tonight (10 min):** add Anthropic API credit + do one dry-run prompt.
2. **~10 min before:** start the two servers, open the dashboard + the deck, paste your key, verify the memory panel is full.
3. **Present (~12–15 min):** 12 slides, with a 4-moment live demo in the middle.

---

## 1. TONIGHT — the one thing that will break the demo if skipped

The red error you saw earlier was **not a bug** — your Anthropic **API** account had **$0 credit**.
A Claude.ai subscription is **separate** from API credit.

- [ ] Go to **console.anthropic.com → Plans & Billing** and add **$5–10** of API credit.
- [ ] Do a **dry run** (see §2 + §3, Moment 1). If a prompt returns a red
      "credit balance is too low" message, the credit isn't active yet — fix it before tomorrow.

> Live-demo model tip: pick **claude-sonnet-5-5** in the dropdown — fast *and* sharp.
> Use **claude-haiku-4-5** if you want it snappier/cheaper; **claude-opus-5-5** for max quality (a bit slower).

---

## 2. Start the app (tomorrow, ~10 min before)

The servers only run while they're started, so start them fresh tomorrow. Open **two terminals**.
These are the exact commands that work on this machine (paste into a terminal):

**Terminal 1 — backend:**
```bash
cd "E:/troubleshooting system/backend" && APP_CORS_ORIGINS="*" .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

**Terminal 2 — frontend:**
```bash
cd "E:/troubleshooting system/frontend" && NEXT_PUBLIC_BACKEND_URL="http://localhost:8080" node node_modules/next/dist/bin/next dev --port 3000
```

Then:
- [ ] Open **http://localhost:3000**
- [ ] Confirm the header says **Andon Assistant** and the **Memory** panel on the right shows **facts: 5, events: 2**.
- [ ] Click **Keys** → paste your `sk-ant-...` key → **Done**. The orange "no key" badge turns green.
- [ ] Set the **provider** dropdown to **Anthropic (Claude)** and the **model** to **claude-sonnet-5-5**.
- [ ] Send one warm-up prompt (Moment 1 below) to confirm real output. Then refresh the page for a clean start.

Health check if anything looks off: open **http://localhost:8080/health** → should say `{"status":"ok"...}`.

> If the memory panel is empty (fresh machine), re-seed it:
> ```bash
> cd "E:/troubleshooting system/backend" && PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_demo.py
> ```

---

## 3. The live demo — 4 moments (exact prompts)

Switch to the dashboard on the **"Meet Andon Assistant"** slide. Run these **in order** — the story builds from *it knows* → *it learns* → *it researches* → *it acts*. Copy-paste the prompts.

**Warm-up (optional) — the calendar is alive:**
> `What preventive-maintenance checks do I have coming up?`
Point at: it lists the two PM events already in memory. "It's not a blank chatbot — it already knows our schedule."

**Moment 1 — It remembers a past fix** *(the key moment)*
> `Station 7 torque gun is throwing fault E-04 again — what do I check first?`
Point at: the **Recall** phase lighting up, then the answer: reset regulator to **6.2 bar**, bleed the line, re-cal, part **RG-14**.
Say: *"It didn't search the internet for that — it recalled what our team logged. That fix is right there in the memory panel."*

**Moment 2 — It learns on the spot**
> `Remember this: on Line 4, a repeating weld-spatter defect is usually a worn electrode cap — dress or replace the cap every 2000 welds.`
Point at: **facts** ticks up in the Memory panel. Then prove it stuck:
> `What causes the repeating weld-spatter defect on Line 4?`
Say: *"Tell it once, and the whole next shift gets it. That's kaizen that doesn't evaporate at shift change."*

**Moment 3 — It researches the unknown** *(takes ~30–45s — narrate while it runs)*
> `I'm getting a Fanuc robot SRVO-062 BZAL alarm on an R-2000 and I've never seen it. Research what it means and how to clear it, with sources.`
Point at: the **tool call** to deep_research, the phases streaming, then a **cited** summary.
Say: *"For a fault nobody here has seen, it pulls current, sourced guidance in under a minute — instead of an hour of searching."*

**Moment 4 — It closes the loop**
> `Schedule a PM check to re-dress the Line 4 weld caps next Monday at 7am.`
> `Write a one-page standard-work sheet for resetting the Station 7 torque-gun regulator and save it as station7-torque-reset.md.`
Say: *"It scheduled the follow-up and wrote a standard-work sheet — standardized work, generated. The file lands in a safe, sandboxed folder, nowhere else."*

Close the demo, return to the deck on **"Built on the way you already work"**.

---

## 4. Slide-by-slide talk track (12 slides, ~12–15 min)

| # | Slide | Say in one line | Note |
|---|---|---|---|
| 1 | Andon Assistant | "A troubleshooting brain that lives on the floor." | ~20s |
| 2 | The problem | "When the line stops, the fix is often in one person's head." | make it their floor |
| 3 | What if the floor had a memory? | The pivot — pause after the question. | |
| 4 | Meet Andon Assistant | One brain, two ways in, your key. | **switch to the app here** |
| 5 | You see every step | The visible turn loop — no black box. | genchi genbutsu |
| 6 | Tools, not just talk | It does work, not just chat. | point at 2 demo rows |
| 7 | Live demo | Cue the 4 moments. | **run the demo (§3)** |
| 8 | Built on the way you work | TPS → features mapping. | earns trust |
| 9 | Your data never leaves the plant | Local-first, private, no per-seat fee. | IT-control angle |
| 10 | Simple enough to trust | Architecture — every box is one file. | keep it light |
| 11 | From a laptop to the whole line | Roadmap — ask what matters to them. | opens the pilot talk |
| 12 | Let's pilot it on one line | The ask — name a line, a 2-week check-in. | then stop talking |

> Replace **[Your name]** / **[email]** on slides 1 and 12 before you present (I left them as placeholders).

---

## 5. If something goes wrong (stay calm — it fails gracefully)

| Symptom | Do this |
|---|---|
| Red "credit balance too low" | Credit isn't active. Add it (console.anthropic.com), or switch the provider dropdown to a funded one (OpenAI/Kimi). |
| Replies feel slow | Switch model to **claude-haiku-4-5** in the dropdown. |
| Deep research is slow / no sources | DuckDuckGo may be rate-limiting. It still answers from general knowledge (fewer citations). Or swap to a quick `Search the web for ...` prompt. |
| A tool errors | The app shows the error inline and keeps going. Just move to the next prompt — don't retry live. |
| Page won't load / stale | Re-run the server command; check http://localhost:8080/health. Hard-refresh the browser. |
| Memory panel empty | Re-run the seed: `cd backend && PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_demo.py`, then refresh. |

---

## 6. Reset between runs
Re-running the demo *keeps* the fixes you taught it (that's fine — even nice, it shows they stuck).
To reset to exactly the 5 seeded facts, just re-run the seed script (it's additive/idempotent).
For a total wipe: close the backend, delete `~/.assistant/state.db`, re-run the seed, restart.

---

## 7. Q&A cheat-sheet (likely group-leader questions)

- **"Does our data go to the cloud?"** — The memory file and your key stay on this machine. Only the question you ask goes to the model provider you choose — and that can be an internal/approved model. Nothing is stored on anyone's server.
- **"Will it make things up?"** — It recalls *our own* logged fixes first and shows every step so you can verify. Research answers come with sources. It's an assistant, not the authority — you still sign off. Automated quality checks are on the roadmap.
- **"What does it cost?"** — No per-seat license. You pay only for model usage — cents per question on a mid model. Runs on a laptop we already have.
- **"Who maintains it / adds the fixes?"** — Anyone can teach it ("remember this…"); it also decides on its own what's worth keeping after each turn. Fixes accrue automatically. Adding a tool is a small, isolated change.
- **"How is this different from ChatGPT?"** — It remembers *our* floor, runs locally and private, calls real tools (calendar, files, research), and shows its work. It's ours.
- **"Does it plug into andon / MES / PLC?"** — Not live yet — it's the #1 roadmap item, and the architecture is built for it.

---

## 8. What's already seeded (so nothing surprises you)
**Facts (past fixes):** Station 7 torque gun E-04 (regulator) · Line 2 conveyor jam (bearing RB-220) · Paint booth humidity alarm (drain) · Station 12 stamping press stroke limit · team answer-style preference.
**Events (upcoming PM):** Station 7 regulator check (Oct 13, 7:00am) · Line 2 bearing replace (Oct 20, 6:30am).
**Skill loaded:** Five-Whys root-cause (recall first → work past the symptom → capture the fix).
