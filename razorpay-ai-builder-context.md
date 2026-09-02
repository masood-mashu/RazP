# Context: Razorpay AI Builder Internship 2026 — Project Brief

## What this is
This is an application for **Razorpay's AI Builder Internship 2026**. It is not a resume-based process — they explicitly evaluate the *work itself*: "We read the work, not the resume." Shortlisted builders skip straight to a panel — no aptitude test, no group discussion.

**Program logistics:**
- Stipend: ₹75,000/month
- Duration: 6 or 12 months, my choice
- Format: In-person, Bangalore, starting September
- Application flow: pick one track → build a real working project against that track's brief → apply

**What they evaluate (their rubric):**
| Dimension | What they're checking |
|---|---|
| Problem taste | Did I pick something that actually matters |
| Build quality | Does it run, is it structured, would they trust it |
| AI judgment | Right tool in the right place — and where I *chose not* to use AI |
| Failure recovery | What broke, and what I did about it |

## My goal
I'm using **Gemini 3.7 Flash inside Antigravity** to design and build the project for this application, working track-by-track from scratch (no prior context assumed). The end deliverable needs to be a **working, structured, demonstrable build** — not a mockup or slide deck — that clearly shows good problem judgment and honest handling of AI's limits and failure cases, since that's explicitly what's being scored.

I need help: (1) picking the strongest track/direction for me to execute well in the time I have, and (2) architecting and building the actual project against that track's stated "bar."

## The 5 tracks (pick one)

### Track 01 — AI Growth & Agentic Commerce
**Grow the merchant's revenue, and make them sellable to AI buyers.**
Build an agent that grows revenue for a merchant on Razorpay test-mode APIs, or that makes a merchant transactable by an AI buyer end to end.
- *Why now:* NPCI's UAP and the global agent-to-agent commerce protocol race (ACP, AP2, x402) make this the open problem of the year; Razorpay's in-app pilots are already live.
- *Example directions:* conversational in-app checkout, agent-readable catalog, upsell & cross-sell agent, campaign orchestrator.
- *The bar:* every money action must be explainable, bounded, and gated. Show the audit trail and one failure handled gracefully.

### Track 02 — AI Risk Manager
**Stop the merchant losing money to fraud, returns, and chargebacks.**
Build a working detector, verifier, or auto-responder for one class of loss, with measured precision and recall on a held-out test set.
- *Why now:* AI-enabled fraud is hitting Indian BFSI while returns/chargebacks quietly eat margin. Surfaces the risk and ML-minded builders others miss.
- *Example directions:* chargeback evidence responder, return-risk scorer, fraud-spike detector, abuse-ring sentinel.
- *The bar:* honest metrics including false-positive cost. Strictly defense-only — anything offense-capable is disqualified.

### Track 03 — AI Revenue Recovery
**Find revenue that's slipping away and win it back.**
Build an agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow — from payment failures and checkout abandonment to overdue receivables.
- *Why now:* revenue loss rarely happens in one clean step (payment degrades → checkout abandoned → subscription fails → invoice overdue). AI can close the loop from detection to diagnosis to intervention to recovery.
- *Example directions:* payment degradation → root cause → recovery action, checkout drop-off recovery, failed-subscription recovery, B2B receivables chaser, mandate retry sequencer, Hinglish voice recovery, promise-to-pay tracker.
- *The bar:* don't just identify the problem — show *measured money recovered* across a batch, with compliant escalation, stopping rules, and an audit trail.

### Track 04 — AI Finance Controller
**Run the books and the cash position.**
Build an agent that closes one finance-ops loop across a 50+ record batch of synthetic data, reporting its match rate and the exceptions it could not resolve.
- *Why now:* 2026 builder consensus is that verification capacity, not generation speed, is the bottleneck. Reconciliation, settlement, and forecasting are still done by hand.
- *Example directions:* multi-source reconciliation, settlement Q&A agent, forward cash forecaster, tax-line matcher.
- *The bar:* throughput + measured accuracy + an honest exception list. One cherry-picked match proves nothing.

### Track 05 — Open Track
**Build what you believe should exist.**
Pick a real problem, use AI meaningfully, and show something that works. Any domain, workflow, or user is fair game.
- *Why now:* the best ideas don't always fit a predefined category.
- *Example directions:* surprise us, solve a problem you deeply understand, build something they haven't thought of.
- *The bar:* open doesn't mean easier — same bar for execution, reliability, and depth applies.

## What I need from you (Gemini)
1. Help me decide which track gives me the best shot given realistic build time and my current skill set (I'll share that separately).
2. Once a track is picked, help me scope a specific, narrow, *finishable* build (not the whole track — one sharp slice of it) that clearly satisfies that track's stated "bar."
3. Architect it with me — data, pipeline, where AI is genuinely load-bearing vs. where a deterministic/rule-based approach is actually the better (and more defensible) choice.
4. Help me instrument it so precision/recall, match rates, recovery amounts, or audit trails — whatever that track's bar demands — are actually measured and shown, not asserted.
5. Push me to think about at least one realistic failure mode and how the system detects/recovers from it, since "failure recovery" is explicitly scored.
