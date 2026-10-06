# Product Requirements Document — Preuve

- **Product:** Preuve — Customer Validation Engine
- **Product type:** B2B SaaS / founder tool
- **Primary purpose:** Validate startup and real-world product ideas using evidence from target markets and structured conversations with potential customers.
- **Initial user:** Solo founder / developer with an idea but no validated customer demand.
- **Initial geography:** US-first, then UK/EU/other markets.
- **Initial operating model:** Human-in-the-loop.

> Implementation decisions (stack, LLM strategy, infra) live in [`ARCHITECTURE.md`](ARCHITECTURE.md)
> and [`adr/`](adr/). Build order lives in [`ROADMAP.md`](ROADMAP.md). Where they differ from
> §29–§32 below, the architecture docs win.

---

## 1. Executive Summary

Preuve is a customer-validation platform that takes a user's raw startup/product idea and guides it through a structured validation pipeline:

```
IDEA
 ↓ PROBLEM HYPOTHESIS
 ↓ TARGET CUSTOMER / ICP
 ↓ MARKET RESEARCH
 ↓ PROBLEM EVIDENCE
 ↓ COMPETITOR / ALTERNATIVE ANALYSIS
 ↓ PROSPECT DISCOVERY
 ↓ PROSPECT ENRICHMENT
 ↓ LEAD SCORING
 ↓ PERSONALIZED RESEARCH OUTREACH
 ↓ HUMAN APPROVAL
 ↓ CUSTOMER RESPONSES
 ↓ RESPONSE ANALYSIS
 ↓ CUSTOMER INTERVIEWS
 ↓ WILLINGNESS-TO-PAY
 ↓ VALIDATION SCORE
 ↓ BUILD / ITERATE / ABANDON
```

The fundamental principle:

> **Do not validate an idea by asking people whether they like it. Validate it by finding people who experience the problem and observing their behavior, responses, commitments, and willingness to pay.**

The product therefore focuses on **evidence collection and decision support**, rather than simply generating cold emails.

## 2. Problem Statement

People frequently generate startup ideas without knowing whether the underlying problem is real, frequent, painful, expensive, underserved, experienced by enough people, or worth paying to solve.

Traditional validation is highly manual. A founder typically has to:

1. Define the target market.
2. Research the industry.
3. Find companies.
4. Find relevant employees.
5. Research those companies.
6. Find evidence of the problem.
7. Contact potential customers.
8. Track responses.
9. Conduct interviews.
10. Analyze responses.
11. Decide whether to build.

This can take weeks and becomes impractical when a founder has dozens of ideas. Existing AI tools generate ideas, landing pages and emails, but don't answer the most important question:

> "Is there enough real-world evidence that I should spend the next 2–6 months building this?"

## 3. Product Vision

Go from *"I have an idea."* to *"Here is the evidence supporting or rejecting this idea."* within days rather than months.

Long-term vision: **the first decision-support layer between an idea and product development.**

## 4. Goals

- **G1 — Validate problems.** Determine whether the proposed problem exists among real potential customers.
- **G2 — Identify the correct customer.** Who experiences the problem, who uses the solution, who pays, who decides.
- **G3 — Gather evidence.** Collect public evidence supporting or contradicting the problem hypothesis.
- **G4 — Find relevant prospects.** Companies and individuals likely to experience the problem.
- **G5 — Facilitate conversations.** Generate highly personalized research outreach.
- **G6 — Analyze responses.** Turn unstructured responses into structured validation data.
- **G7 — Produce a decision.** Recommend `BUILD` / `ITERATE` / `INVESTIGATE FURTHER` / `ABANDON` with explainable reasoning.

## 5. Non-Goals

The initial product will not:

- automatically build the startup;
- automatically close sales;
- send thousands of unsolicited emails;
- impersonate a company or founder;
- guarantee that an idea will succeed;
- fabricate customer evidence;
- pretend that AI-generated assumptions are market validation;
- replace human customer interviews;
- scrape private or unauthorized information;
- become a generic CRM;
- become a generic email-marketing platform.

## 6. Target Users

- **Primary — Solo founder.** E.g. a developer with 10–30 ideas who can build software but doesn't know which has genuine demand. Needs fast validation, evidence, prospect discovery, structured interviews, objective decision support.
- **Secondary — Startup team (2–5 people).** Needs shared research, collaboration, experiment tracking, evidence management.
- **Future — Product manager** evaluating new products or features.
- **Future — Startup studio / incubator** evaluating dozens or hundreds of ideas.

## 7. Core Product Concept

Everything revolves around an **Idea Validation Workspace**. Each idea becomes a project:

```
┌─────────────────────────────────────────────┐
│ Construction Progress Automation            │
│ Status: VALIDATING        Score: 76/100 🟢  │
│ ICP: US mid-market construction companies   │
│ Evidence: 38    Prospects: 127              │
│ Outreach: 31    Responses: 9                │
│ Interviews: 4   Positive signals: 6         │
│ Recommendation: CONTINUE VALIDATION         │
└─────────────────────────────────────────────┘
```

## 8. Stage 1 — Idea Submission

User enters:

- **Idea** — e.g. "AI tool that automates construction progress reports."
- **Target market** — e.g. US.
- **Why I think this matters** — e.g. "Project managers spend too much time creating reports."
- Optional: geography, industry, customer type, expected business model, known competitors, user's assumptions.

## 9. Idea Analyzer

AI converts the raw idea into a structured hypothesis:

| Field | Example |
|---|---|
| Problem | Construction project teams spend significant time manually compiling progress reports. |
| Potential users | Project managers |
| Potential buyer | Director of Operations |
| Potential economic value | Reduction in reporting labor |
| Geography | United States |
| Industry | Construction |

It also identifies **unknowns**, which become the research plan:

1. How frequently does this happen?
2. How much time is spent?
3. What tools are currently used?
4. Is the problem expensive enough to justify software?
5. Who controls the budget?
6. Are existing solutions sufficient?

## 10. ICP Generator

Generates one or more candidate ICPs, each with a hypothesis score:

- **ICP A** — US construction companies, 50–500 employees, 10+ active projects.
- **ICP B** — US general contractors, 500–2,000 employees, multi-state operations.
- **ICP C** — Specialized construction firms, 50–200 employees, high reporting requirements.

## 11. Market Research Engine

Gathers publicly available information from: company websites, public search results, job postings, industry publications, public forums, Reddit, reviews, news, documentation, public reports, public directories.

Searches for evidence of: problem existence, problem frequency, existing workflow, existing alternatives, complaints, manual processes, technology adoption, hiring requirements, industry trends.

## 12. Evidence Engine

Every discovered evidence item becomes a structured record:

`Evidence ID · Source · URL · Company · Date · Evidence type · Extracted statement · Relevance · Confidence · Related hypothesis`

Example — *Company:* ABC Construction · *Source:* Job posting · *Observation:* "Project coordinator responsible for preparing weekly project reports." · *Type:* Manual workflow · *Relevance:* HIGH · *Confidence:* 0.89

The system **must** distinguish between:

- **Fact** — "Public job listing explicitly mentions weekly reporting."
- **Inference** — "This may indicate reporting is operationally significant."
- **AI assumption** — "Construction companies probably have this problem."

These must never be presented as equivalent evidence.

## 13. Competitor & Alternative Analysis

Identifies:

- **Direct competitors** — products solving the same problem.
- **Indirect competitors** — different software solving part of the problem.
- **Manual alternatives** — Excel, Google Sheets, email, paper, WhatsApp, internal tools.
- **Service alternatives** — consultants, agencies, freelancers.

Key question: **"How is the problem currently being solved?"** — often more useful than a competitor list.

## 14. Prospect Discovery

Input: ICP (e.g. US construction companies, 50–500 employees).
Output per company: Company · Website · Location · Industry · Estimated size · Relevant evidence · Source.

## 15. Prospect Enrichment

For every company: Website → Industry → Size → Location → Technology → Services → Public evidence → Relevant roles.

Potential contacts: founder, owner, operations director, project manager, VP operations, department head.
Prioritize **professional relevance**, not maximum email count.

## 16. Lead Scoring

Explainable score per prospect:

| Factor | Points |
|---|---|
| Company fit | 20 |
| Problem evidence | 25 |
| Role relevance | 20 |
| Company size | 10 |
| Geography | 5 |
| Technology fit | 10 |
| Other signals | 10 |
| **Total** | **100** |

Example: *Sarah Johnson, Director of Operations, ABC Construction — 91/100.* Reasons: ✓ company matches ICP ✓ relevant decision-making role ✓ public evidence of manual reporting ✓ operates multiple projects ✓ geographic match.

## 17. Outreach Generation

Research-oriented outreach, **not** generic sales spam. Every message should:

- identify the recipient;
- explain why they were selected;
- reference legitimate public evidence where appropriate;
- explain the research purpose;
- ask a small question;
- avoid exaggerated claims;
- avoid pretending the product already exists if it doesn't.

## 18. Human Approval Gate

Every outbound message starts as `DRAFT`. The user sees prospect, lead score, evidence, suggested message, and can **EDIT / APPROVE / REJECT**. Only approved messages can be sent — for quality, trust, deliverability, compliance, and avoiding accidental misinformation.

## 19. Outreach Experiment

Tracks: sent, delivered, bounced, opened (where reliably available), replied, positive reply, negative reply, interview booked.

Open rate is **not** validation. The important signals are:
**meaningful replies → interviews → problem confirmation → commitments → payment.**

## 20. Response Intelligence

Incoming responses are classified. Example:

> "We actually have this problem every week. Our PMs spend about 4–5 hours creating reports. We currently use Excel and photos from WhatsApp."

Extracted: Problem confirmed: YES · Frequency: Weekly · Current solution: Excel + WhatsApp · Time cost: 4–5 h/week · Pain severity: HIGH · Existing solution satisfaction: LOW · Interest: HIGH · Recommended action: INTERVIEW.

## 21. Conversation Intelligence

For longer conversations, extract: **Problem** (what is painful), **Workflow** (how solved today), **Frequency**, **Cost** (time/money), **Existing alternatives**, **Trigger** (when it becomes urgent), **Buyer** (who pays), **Decision process**, **Objections**, **Desired solution**.

## 22. Interview Workspace

Structured interview guide generated from unknowns. Example:

- *Interview #4 — Sarah, Operations Director*
- *Known:* reports take ~4 h/week.
- *Unknown:* who approves reports?
- *Question:* "Can you walk me through what happens after your PM finishes the report?"
- *Follow-up:* "Where does most of the manual work happen?"

The goal is to **learn**, not lead the customer toward agreeing with the founder.

## 23. Willingness-to-Pay Validation

After sufficient problem evidence: problem confirmed → current cost understood → existing alternatives understood → pricing conversation.

Records: customer, current spending, estimated problem cost, expected price, stated willingness, actual commitment.
Strongest signal: *"I'll pay for it."* followed by an actual payment or signed commitment.

## 24. Validation Scoring

| Dimension | Weight |
|---|---|
| Problem evidence | 20% |
| Problem frequency | 10% |
| Problem severity | 15% |
| Customer response | 15% |
| Interview confirmation | 15% |
| Existing alternatives | 10% |
| Willingness to pay | 15% |
| **Total** | **100** |

## 25. Validation States

- 🔴 **UNVALIDATED** — insufficient evidence.
- 🟡 **RESEARCHING** — market research underway.
- 🟡 **EARLY SIGNAL** — some positive evidence.
- 🟢 **PROBLEM VALIDATED** — multiple independent customers confirm the problem.
- 🟢 **SOLUTION VALIDATION** — customers express strong interest in the proposed solution.
- 🟢 **COMMERCIAL VALIDATION** — customers demonstrate willingness to pay.
- 🚀 **MVP READY** — enough evidence to justify building.

## 26. Decision Engine

Example output:

```
Score: 78/100
Recommendation: CONTINUE → BUILD MVP

Strong evidence:
• 17 prospects confirmed the problem
• 8 use manual workflows
• 5 spend >3 hours/week
• 4 requested to see a solution
• 2 agreed to pilot

Weak evidence:
• Pricing validation limited
• Buyer role uncertain

Next action: Interview 5 operations directors.
```

The system **must explain why** it recommends something.

## 27. Multi-Idea Portfolio

Dashboard of all ideas with score and state (e.g. Construction AI 82 🟢, Legal Automation 77 🟢, Retail Analytics 64 🟡, Restaurant AI 52 🟡, Gym Automation 39 🔴). Compare validation score, evidence, responses, interviews, potential market, willingness to pay.

## 28. Experiment Management

Each idea contains experiments, turning validation into a scientific process:

- **Experiment #1** — Hypothesis: construction PMs struggle with manual reporting. ICP: US construction, 50–500 employees. Sample: 20 prospects. Result: 7 positive responses. Conclusion: promising.
- **Experiment #2** — Hypothesis: operations directors are better buyers than PMs. Result: ops directors produced 2× more positive responses. Conclusion: update ICP.

## 29. Recommended Technical Architecture (original suggestion)

```
                 FRONTEND (Next.js / React)
                          │
                     API Gateway
        ┌─────────────────┼─────────────────┐
   Idea Service     Research Service     Outreach
        │                 │                 │
   PostgreSQL       Search Workers     Email Provider
        │                 │
        │           Evidence Store
   Validation Engine
        │
    AI / LLM Layer
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the actual implementation (modular monolith).

## 30. Backend Services

`ideas/ research/ evidence/ competitors/ prospects/ enrichment/ scoring/ outreach/ responses/ interviews/ validation/ notifications/`

## 31. Asynchronous Architecture

Research must not happen inside a normal HTTP request:

`POST /ideas/123/research → Queue → Research Worker → Search sources → Extract evidence → Store results → Update progress`

Redis + a worker queue is enough initially.

## 32. Database

PostgreSQL. Core tables: users, ideas, hypotheses, icps, research_runs, evidence, competitors, companies, contacts, prospects, lead_scores, outreach_campaigns, messages, responses, interviews, interview_notes, validation_scores, experiments.

## 33. Data Model Relationship

```
User
 └── Idea
      ├── Hypotheses
      ├── ICPs
      ├── Evidence
      ├── Competitors
      ├── Prospects
      │     └── Outreach
      │            └── Responses
      ├── Interviews
      ├── Experiments
      └── Validation Score
```

## 34. AI Layer

Structured extraction · Classification · Summarization · Personalization · Response analysis · Interview assistance · Validation synthesis.

## 35. AI Guardrails

**AI must never fabricate evidence.** Every AI-generated claim should have: Claim → Source → Evidence.
If there is no evidence, the system says **"No evidence found."** — not "Companies commonly experience…".

## 36. Outreach Safety / Deliverability

Preuve must not become a mass-spam platform. Constraints: human approval, sending limits, bounce monitoring, suppression lists, unsubscribe handling, domain authentication guidance, duplicate prevention, contact frequency limits, transparent sender identity, no fake company identities.
Priority: **quality of conversations over number of emails.**

## 37. Privacy & Compliance

- only use legitimately accessible data;
- respect applicable terms and restrictions;
- minimize stored personal information;
- provide deletion mechanisms;
- maintain suppression lists;
- avoid sensitive personal data;
- track source/provenance;
- respect applicable email marketing and privacy laws.

Legal review is required before scaling US/EU outreach.

## 38. Dashboard

Totals (ideas, active validations, interviews, positive signals) plus a table of ideas with score and status.

## 39. Idea Detail Page

Score and status; problem; ICP; evidence summary (items, companies, positive responses); customer validation funnel (contacted, responded, confirmed problem, interviews, pilot requests); next actions.

## 40. Research Explorer

List of evidence with strength, type, company and quote. Clicking shows source, date, extracted information, why it's relevant, associated hypothesis.

## 41. Prospect Explorer

Ranked prospect list with filters: country, industry, company size, role, score, evidence, contact status, response status.

## 42. Email Workspace

Prospect, why selected (score), evidence, subject, message; actions **EDIT / APPROVE & SEND / REJECT**.

## 43. Response Intelligence Dashboard

Sent / replies / positive / neutral / negative; problem confirmed / interview requested / pilot interest; most common pain.

## 44. Validation Report

Generated at the end of an experiment: idea, verdict, score, problem/solution/WTP status, evidence count, conversations, interviews, strongest signal, biggest uncertainty, recommendation. One of the most valuable artifacts in the system.

## 45. MVP Scope

- **Phase 1:** Idea input → ICP generation → Research → Evidence collection → Company discovery → Prospect scoring → Dashboard
- **Phase 2:** Personalized outreach → Human approval → Email sending
- **Phase 3:** Response collection → Response analysis → Interview tracking
- **Phase 4:** Validation scoring → Decision engine → Validation report

## 46. MVP Success Criteria

Take one completely new idea and, in reasonable time, produce: ICP, problem hypotheses, evidence, competitors, 20+ relevant prospects, lead scores, personalized outreach, structured responses, validation report.

## 47. Metrics

- **Research efficiency** — manual vs automated research time.
- **Prospect relevance** — % of prospects that actually match the ICP.
- **Response rate** — meaningful responses / delivered outreach.
- **Problem confirmation rate** — customers confirming problem / meaningful conversations.
- **Interview conversion** — interviews / positive responses.
- **Commercial validation** — customers willing to pay / qualified conversations.

## 48. North-Star KPI

Don't optimize for emails sent, companies scraped, or AI-generated messages.
**North star: validated customer conversations per idea.**

## 49. Future Features

Automated experiment generation · ICP A/B testing · messaging experiments · pricing experiments · landing-page experiments · waitlist validation · pre-order validation · CRM integration (HubSpot, Salesforce) · multi-user teams · autonomous validation agent ("Research this idea and tell me whether it deserves an MVP").

## 50. The Ultimate Version

A single input — *"What are you thinking of building?"* + market — then live progress (ICP identified, companies discovered, evidence found, competitors identified, prospects selected, outreach prepared), ending in a validation result with score, problem status, conversation funnel, recommendation and concrete next steps.

## 51. Core Philosophy

Don't build an AI that tells founders *"Your idea is great."*
Build an AI that is willing to tell them **"Your idea has weak evidence. Don't build it yet."**

```
20 IDEAS → AUTOMATED RESEARCH → 5 PROMISING → CUSTOMER OUTREACH
        → 2 PROBLEM-VALIDATED → 1 COMMERCIAL VALIDATION → BUILD → REAL CUSTOMERS
```
