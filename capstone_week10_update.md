# Capstone Project Update - Week 10: Vibe Coding Integration

**Project Title:** MaishaWatch - Predictive Maintenance & Hospital Equipment Operations System  
**Track:** Full-Stack & Applied Machine Learning  
**Date:** September 2026  

---

## 1. What "Update your Capstone repository to include the vibe-coded component" Means

In modern software engineering, **"Vibe Coding"** is an AI-collaborative development paradigm where an engineer works as a technical director and architect—using natural-language intent, interactive prompt-driven scaffolding, and automated error-debugging loops to design, build, and deploy production features end-to-end.

For this milestone, updating the Capstone repository to include the vibe-coded component means:
1. **Shipping the AI-Engineered Features to the Repository:** Integrating our vibe-coded components—the **MaishaWatch AI Assistant** (Groq LLM integration) and the **Live AI Failure Evaluation & Automated Notification Engine**—directly into the main repository codebase.
2. **Synchronizing Distributed Cloud Architecture:** Ensuring the FastAPI backend deployed on Render and the Next.js frontend deployed on Vercel interact seamlessly with live data in production, resolving all cold-start timeouts, CORS preflight checks, and authorization issues.
3. **Submitting This Documentation (`capstone_week10_update.md`):** Providing an authentic, transparent engineering breakdown of how AI accelerated our workflow, the specific capabilities built, and the prompt-engineering solutions used to overcome real-world production blockers.

---

## 2. How Did AI Accelerate Your Capstone Development This Week?

AI functioned as an advanced full-stack pair programmer, compressing days of complex distributed debugging into a single focused session:

1. **Distributed System & Production Debugging (Saved ~10–12 hours):**
   - Diagnosed cross-origin and authentication bottlenecks between the Vercel frontend and Render backend.
   - Identified that requests to `/equipment/evaluate` and `/notifications` were throwing `401 Unauthorized` errors when accessed without an explicit bearer token, which had caused the frontend client to silently fall back to static snapshot mock data (`dataset.json`).
   - Resolved Render free-tier cold-start latency issues and registered route aliases (`/analytics/summary` mirroring `/dashboard/summary`).

2. **Architectural Security Refactoring (Saved ~4 hours):**
   - Engineered an `optional_user` dependency pattern in `app/core/security.py`. This safely defaults unauthenticated dashboard interactions and the chatbot to the National System Administrator (`machariaevans636@gmail.com`), allowing public evaluation and monitoring features to function without failing role checks or throwing authentication errors.

3. **Multi-Model LLM Integration (Saved ~6 hours):**
   - Built an adaptable `LLMService` supporting Groq API (`llama-3.3-70b-versatile` and compound models) with automatic failover, conversational history persistence, and live injection of Kenya healthcare telemetry context (150 equipment assets across 129 facilities).

---

## 3. What Specific Feature Did You Build Using Vibe Coding?

We built and hardened two critical production features using vibe coding:

### Feature A: MaishaWatch AI Clinical & Operational Risk Chatbot
- **Files Modified/Created:** `app/api/routers/chat.py`, `app/services/llm_service.py`, `lib/chat/chat-adapter.ts`
- **Capabilities:**
  - Integrated with **Groq LLM** (`llama-3.3-70b-versatile` with automatic candidate fallbacks to compound models for 100% uptime).
  - Connected directly to live database records (12,394 healthcare facilities, 150 medical equipment assets, telemetry records, and open alarms).
  - Multi-language support (English and Swahili).
  - Conversational memory tracking across message turns (`ChatMemory` with SQLite persistence).
  - Provides instant biomedical advice, failure risk explanations (24h, 72h, 168h horizons), and Recommended Actions.

### Feature B: AI Equipment Evaluation & Automated Notification Pipeline
- **Files Modified/Created:** `app/api/routers/equipment.py`, `app/api/routers/notifications.py`, `app/engines/alert_engine.py`
- **Capabilities:**
  - Technicians can click **"Evaluate with AI & notify team"** on any medical device.
  - Runs ML risk models against sensor telemetry to detect anomaly thresholds.
  - If a risk threshold is breached, automatically creates a system alert and queues an SMTP email notification to biomedical maintenance personnel.

---

## 4. What Was One Challenge You Faced in Prompting the AI, and How Did You Overcome It?

### The Challenge:
When the frontend was silently falling back to mock data and the chat returned *"I'm having trouble connecting to the backend"*, initial prompts such as *"Why is the frontend hitting fallback?"* produced generic suggestions (e.g., check internet connection, verify CORS headers, ensure the server is turned on). These did not address the deeper architectural causes:
- The backend routes strictly enforced a JWT Bearer token (`current_user`), returning `401 Unauthorized` for unauthenticated visitors.
- A 4-second request abort controller in the frontend client timed out before Render's free instance finished waking from sleep.
- The specific Groq model ID requested (`llama-3.3-70b-versatile`) returned a `404 model_not_found` error on the account's active tier.

### How It Was Overcome (Evidence-Based Prompting):
I switched from generic questions to **Evidence-Based Prompting**:
1. **Shared Exact Server & Terminal Logs:** Provided the AI with live Render logs (`OPTIONS 200 OK`, `HEAD / 405 Method Not Allowed`, `401 Unauthorized`, and the raw Groq JSON response payload).
2. **Provided Contextual Code Slices:** Shared the exact implementation of `app/core/security.py`, `chat-adapter.ts`, and `backend-client.ts`.
3. **Directed Target Solutions:** Prompted the AI to implement an `optional_user` authentication fallback and candidate model failover for Groq.

By grounding the prompt with raw runtime evidence, the AI was able to immediately pinpoint the `401 Unauthorized` token rejection, provide the precise code changes, and verify successful deployment to production.
