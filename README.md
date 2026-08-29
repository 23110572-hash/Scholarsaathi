# ScholarSaathi

**One trusted scholarship journey—from discovery to decision.**

## Live Platform

- **Web application:** https://scholarsaathi-two.vercel.app
- **API:** https://scholarsaathi.onrender.com

## Demo Credentials

Use these to sign in on the live web application and explore the student journey.

### Student

| Field | Value |
| --- | --- |
| Email | `krishnaagrawal0706@gmail.com` |
| Password | `12345678` |

Sign in at [`/login/student`](https://scholarsaathi-two.vercel.app/login/student). After logging in you can browse the scholarship catalog, ask the AI assistant about eligibility, save opportunities, and prepare an application.

### Provider

| Field | Value |
| --- | --- |
| Email | `central.publisher@demo.scholarsaathi.local` |
| Password | `Demo@ScholarSaathi2026` |

Sign in at [`/login/organization`](https://scholarsaathi-two.vercel.app/login/organization). After logging in you can view your organization dashboard, manage published scholarships, and review student applications.

> These are shared demo accounts on synthetic data. Do not store personal information in them, and do not reuse these passwords anywhere else.

## Problem

Scholarship information is fragmented across portals, PDFs, notices, and provider websites. Students struggle to understand whether they qualify, which information is current, and what to do next. Generic AI search can make this worse by mixing rules between schemes or presenting guesses as facts.

Providers face a different problem: publishing structured, verifiable scholarship information and managing applications usually requires disconnected tools. This creates outdated listings, repeated paperwork, low trust, and missed opportunities for deserving students.

## Our Solution

ScholarSaathi is a unified platform where scholarship providers publish and confirm their own programme information, while students discover relevant opportunities through an evidence-grounded AI assistant.

Students receive clear matching guidance, source-backed explanations, application checklists, and status tracking. Providers receive a dedicated workflow to create scholarships, confirm source evidence, publish opportunities, and review applications.

## How It Works

1. **Provider-owned publishing** — Central, state, NGO, and private providers create structured scholarship records and confirm the evidence used by the platform.
2. **Privacy-conscious discovery** — Students share only the academic and eligibility details needed for matching, without sensitive identity documents.
3. **Evidence-grounded AI** — The assistant evaluates each scholarship independently and cites only provider-confirmed source passages.
4. **Honest uncertainty** — Missing or conflicting evidence produces a clear “cannot determine” response instead of a fabricated answer.
5. **Complete application journey** — Students can save opportunities, prepare applications, submit them, and follow provider decisions in one place.

## What Makes ScholarSaathi Unique

- **Evidence before answers:** every meaningful AI claim must point to provider-confirmed evidence.
- **No cross-scholarship contamination:** rules and citations are isolated by scholarship version and provider ownership.
- **Provider accountability:** organizations control publication, confirmation, and final decisions.
- **AI with deterministic guardrails:** LangGraph workflows validate scholarship IDs and citation IDs after generation; unsafe output is rejected automatically.
- **End-to-end experience:** discovery, explanation, application, review, and status tracking live in one product.
- **Built for India’s scholarship ecosystem:** the architecture supports central government, state government, NGO, and private programmes without mixing ownership boundaries.
- **Accessible guidance:** complex conditions can be explained in a student’s preferred language while preserving the original source evidence.

## Responsible AI Approach

ScholarSaathi uses LangChain, LangGraph, and Groq for structured scholarship assessment and question answering. AI never publishes a scholarship, invents an eligibility rule, or makes an official selection decision. Deterministic validation checks every generated scholarship reference and citation before a response reaches the student.

When evidence is incomplete, the assistant directs the student to the provider source or helpdesk. The provider always remains the final authority.

## Impact

ScholarSaathi can reduce the time students spend searching across unreliable sources, improve confidence in scholarship guidance, and help providers reach eligible applicants with clearer information. The result is fewer missed opportunities, fewer avoidable application errors, and a more transparent scholarship ecosystem.

## Vision

Our goal is to make every scholarship opportunity understandable, verifiable, and accessible—so that a student’s future is not limited by fragmented information or confusing processes.
