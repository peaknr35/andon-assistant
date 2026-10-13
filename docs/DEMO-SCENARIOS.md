# Andon Assistant — Demo Scenario & Prompt Bank

If you (or the group leader) aren't sure what to ask next, grab any prompt below — all are
copy-paste. Grouped by what each one shows. Provider **Anthropic**, model **claude-sonnet-5-5**.

> **The strongest move:** hand the keyboard over. Ask the group leader to name a *real*
> recurring fault on their line, type it in, and let recall/research answer it live. Their
> own problem answered in front of them beats any scripted moment.

---

## A. It already knows our fixes  (recall — uses the seeded memory)
One prompt per fix already in memory. Watch the **Recall** phase light up; the answer is the
team's own logged fix, not a web search.

> Station 7 torque gun is throwing E-04 again — what do I check first?

> Line 2 keeps jamming at the transfer point. What's the usual cause and fix?

> The paint booth humidity alarm is going off above 65%. What do I do?

> How fast can we safely run the Station 12 stamping press, and why?

**Say:** *"It didn't Google any of that — that's what our team logged. See the Memory panel."*

---

## B. It learns on the spot  (teach → prove it stuck)
Teach a new fix, watch **facts +1**, then ask it back. Keep the station name in the question
so recall has a hook.

**Teach:** `Remember this: on Line 4, a repeating weld-spatter defect is usually a worn electrode cap — dress or replace the cap every 2000 welds.`
**Prove:** `What causes the repeating weld-spatter defect on Line 4?`

**Teach:** `Remember this: the Station 3 nutrunner drops to idle when the 24V supply dips — check the terminal block before swapping the tool.`
**Prove:** `Why does the Station 3 nutrunner keep dropping to idle?`

**Say:** *"Tell it once; the whole next shift gets it. Kaizen that doesn't evaporate at shift change."*

---

## C. Root-cause, the Toyota way  (the built-in 5-Whys skill)

> Walk me through a 5-Whys root cause for repeated scrap on the Station 12 press.

> Use 5 Whys on the Line 2 transfer-point jams and recommend a countermeasure.

**Watch for:** it recalls the known cause first, then works past the symptom. **Say:** *"Same
method we already use — it just never forgets a step."*

---

## D. It researches the unknown  (web / deep research · ~10–15s)
For a fault nobody here has seen. Expect a tool call and a **cited** answer.

> I'm getting a Fanuc robot SRVO-062 BZAL alarm on an R-2000 and I've never seen it. Research what it means and how to clear it, with sources.

> A Siemens S7 PLC is showing a red SF (system fault) LED. What does it usually mean and how do I start diagnosing it? Cite sources.

> A proximity sensor on the conveyor keeps false-triggering. What are the common causes and fixes?

**Fallback (faster/lighter if search is slow):** `Search the web for how to clear a Fanuc SRVO-062 BZAL alarm.`

**Say while it runs:** *"It's planning, searching, and writing — the hour of Googling it saves."*

---

## E. It schedules & writes standard work  (calendar + files)

**Schedule:** `Schedule a PM check to re-dress the Line 4 weld caps next Monday at 7am.`
**Confirm:** `What preventive-maintenance checks do I have coming up?`  → your seeded PMs **plus** the new one.
**Standard work:** `Write a one-page standard-work sheet for resetting the Station 7 torque-gun regulator and save it as station7-torque-reset.md.`
**Another:** `Write a shift-handover checklist for Line 2 and save it as line2-handover.md.`

**Say:** *"Follow-up scheduled, standard work generated — and it can only write inside one safe folder, nowhere else on the machine."*

---

## F. It remembers how you like to work  (preferences)

**Teach:** `Remember that I want answers as a short numbered checklist, most-likely cause first, with the part number.`
**Then ask anything from section A** — the format sticks.

**Teach:** `Remember that our shift starts at 6am and PM windows are the first 30 minutes.`
**Then:** `When should I schedule the Line 2 bearing replacement?`

---

## G. Open-ended starters  (hand these to the group leader)

> What can you help me with on the floor?

> What do you already know about our lines so far?

> Summarize the recurring issues you've seen.

> I'm training a new team member on Station 7 — what should they know?

---

## H. When the group leader pushes back  (have the answer ready)

| They ask | Type / point at | Say |
|---|---|---|
| "How do I know that's right?" | the **Recall** step + Memory panel (our own log), or the **sources** on a research answer | "It's not guessing — that's our log. For new stuff it shows sources, and you still sign off." |
| "Where did that come from?" | the Memory panel (facts) / the source links | "Right here — what the team logged, or the cited pages." |
| "What if it's wrong?" | the visible step-by-step phases | "You verify — it just surfaces the likely cause in seconds and shows its work." |
| "Does our data go to the cloud?" | — | "No. The memory file and the key stay on this laptop." |
| "What does it cost?" | — | "Cents per question, no per-seat license. Runs on a laptop we already have." |
| "Can it do MY line?" | **hand them the keyboard** | "Name a fault you keep seeing — type it in." |

---

## Quick-grab one-liners  (stuck? just pick one)
- `Station 7 torque gun is throwing E-04 again — what do I check first?`
- `Line 2 keeps jamming at the transfer point. What's the usual cause?`
- `Remember this: <your fix in one sentence>.`  → then ask it back
- `Research what a Fanuc SRVO-062 BZAL alarm means and how to clear it, with sources.`
- `Walk me through a 5-Whys root cause for <problem>.`
- `Schedule a PM check for <task> next Monday at 7am.`
- `What preventive-maintenance checks do I have coming up?`
- `Write a standard-work sheet for <task> and save it as <name>.md.`
- `What do you already know about our lines?`
- `Summarize the recurring issues you've seen.`
