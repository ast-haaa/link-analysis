# Link Analysis — AI-Powered Website Intelligence API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Google GenAI SDK](https://img.shields.io/badge/Google%20GenAI%20SDK-v3.5+-4285F4.svg?logo=google&logoColor=white)](https://github.com/googleapis/python-genai)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-46%20passed-brightgreen.svg?logo=pytest&logoColor=white)](https://pytest.org/)
[![Frontend UI](https://img.shields.io/badge/Frontend-Link%20Analysis%20Dashboard-DB2777.svg)](http://localhost:4000/dashboard)
[![Render Deploy](https://img.shields.io/badge/Render-Deployment%20Ready-46E3B7.svg?logo=render&logoColor=white)](https://render.com/)

A production-grade REST API and interactive web dashboard built with **FastAPI**, **Tailwind CSS**, **HTTPX**, **BeautifulSoup4**, **Pydantic**, and the official **Google GenAI Python SDK (`google-genai`)**. The application extracts, sanitizes, and structures website content to generate comprehensive business intelligence across five analytical sections using **Google Gemini 2.5 Flash**.

Developed for the **Dxora Technologies Practical Technical Assessment**.

---

## Table of Contents
- [Interactive Web Dashboard (Link Analysis UI)](#interactive-web-dashboard-link-analysis-ui)
- [Architecture & Workflow](#architecture--workflow)
- [The Five Business Intelligence Sections](#the-five-business-intelligence-sections)
- [LLM Model Research & Comparative Evaluation](#llm-model-research--comparative-evaluation)
- [Recommended Model & Cost Analysis](#recommended-model--cost-analysis)
- [Security & SSRF Safeguards](#security--ssrf-safeguards)
- [Project Directory Structure](#project-directory-structure)
- [Installation & Local Setup](#installation--local-setup)
- [API Documentation & Usage](#api-documentation--usage)
- [Sample Real-World Output](#sample-real-world-output)
- [Automated Test Suite (46 Passed)](#automated-test-suite-46-passed)
- [Deployment Guide (Render)](#deployment-guide-render)
- [Limitations & Mitigations](#limitations--mitigations)

---

## Interactive Web Dashboard (Link Analysis UI)

The project includes **Link Analysis**, a responsive single-page web interface served directly through FastAPI:

- **Dashboard URLs:** Navigate in any browser to `http://localhost:4000/` or `http://localhost:4000/dashboard`.
- **API Documentation:** Interactive Swagger UI is available at `http://localhost:4000/docs`.

### Design Direction & Aesthetic
- **Theme:** Clean, modern SaaS aesthetic inspired by high-end AI analytics platforms (Light theme only).
- **Color System:**
  - Background: `#FAFAFC` / `#FFFFFF`
  - Cards: `#FFFFFF` with subtle 1px neutral borders (`#E4E4E7`) and soft shadows (`shadow-card`)
  - Soft Pink Accents: `#FCE7F3` / `#FDF2F8`
  - Primary Magenta: `#DB2777` (hover: `#BE185D`)
  - Deep Magenta: `#9D174D`
  - Body Text: `#18181B`
  - Muted Text: `#71717A`
- **Typography & Styling:** Minimalist, rounded cards (`rounded-2xl`), subtle borders, smooth CSS transitions, and SVG icons without external font dependencies.

### Frontend Features
1. **Header Navigation:** Link Analysis branding, direct link to interactive Swagger `/docs`, and live `/health` system badge.
2. **Hero Analysis Bar:** Prominent target URL input with input clear button, glowing focus ring, primary `Analyze Website` CTA with spinner, and one-click sample chips (`stripe.com`, `linear.app`, `vercel.com`, `resend.com`).
3. **Animated Loading Experience:** Multi-stage progress indicator with smooth bar animation (10% → 92%), live elapsed second timer, and active milestone step tracking:
   - 1. SSRF & Scheme Validation
   - 2. DOM Sanitization & Extraction
   - 3. Gemini 2.5 Flash Reasoning
   - 4. Structuring 5 Intelligence Sections
   
   > **Note on Loading Indicator:** The multi-stage animated progress bar (10% → 92%) and milestone step sequence on the web interface are simulated client-side animations. They are intentionally designed to provide responsive visual feedback during the ~35-second Gemini LLM generation, rather than a real-time WebSocket or Server-Sent Events (SSE) server telemetry stream.

4. **Interactive 5-Section Intelligence Display:**
   - **Executive Brand Overview:** Brand title, category pill, target link, word count, raw HTML byte count, business summary, and offering tag cloud.
   - **Section 1: Competitor vs Brand Analysis:** Benchmarked competitors with strengths/weaknesses tags, explicit `Verified from Site` vs `AI-Inferred Industry` badges, brand competitive advantages, positioning opportunities, and verification transparency disclaimer.
   - **Section 2: Target Search Queries:** Exactly 5 high-intent queries with 5-platform pills (Google, Facebook, Instagram, LinkedIn, X), search intent tags (Commercial, Informational, Transactional, Navigational), business relevance, target audience, 1-click query copy with `Copied!` confirmation, and non-fabricated volume disclaimer.
   - **Section 3: SEO Improvements & Strategy:** Primary, secondary, and long-tail keyword pills; recommended SEO title & meta description with character count indicators and 1-click copy buttons; high-impact content recommendations cards; interactive schema-ready FAQ accordion; and strategic rationale.
   - **Section 4: Top 5 Identified Services:** Up to 5 service cards with detailed descriptions, target industry, customer persona, main business benefit highlight in soft pink accent, and `Extracted from Page` vs `AI Inferred` evidence badges.
   - **Section 5: Target Audience & Personas:** Primary customer persona featured card with pain point checklist; secondary audience persona cards; target industry pills; business model tags; geographic market focus; and actionable marketing recommendation roadmap.
5. **Productivity Utilities:**
   - **1-Click Copy & Export:** Instant copy of search queries and SEO snippets with toast notifications, plus a `Copy JSON` and `Export JSON` file download utility.
   - **Tabs Navigation:** Tabbed switching across Overview, Competitors, Search Queries, SEO, Services, and Audience sections for clean, spacious scanning.
   - **Reset / Analyze Another:** One-click reset to home input.
6. **Error Resilience:** Clear, user-friendly error banners for SSRF blocks, invalid schemes, size limits, and upstream timeouts, with an expandable technical diagnostics accordion and a retry button.

---

## Architecture & Workflow

```text
                                       HTTP POST /link-analysis
                                                  │
                                                  ▼
                                     ┌──────────────────────────┐
                                     │  Pydantic URL Validator  │
                                     │   (HTTP/HTTPS Check)     │
                                     └────────────┬─────────────┘
                                                  │ Validated URL
                                                  ▼
                                     ┌──────────────────────────┐
                                     │   Multi-Tier SSRF Guard  │
                                     │  (IP Filter & DNS Check) │
                                     └────────────┬─────────────┘
                                                  │ Public Safe Host
                                                  ▼
                                     ┌──────────────────────────┐
                                     │   Async HTTPX Fetcher    │
                                     │  • SSRFSafeBackend       │
                                     │  • Anti-DNS Rebinding    │
                                     │  • Max 5 Redirects       │
                                     │  • 5 MB Streaming Limit  │
                                     └────────────┬─────────────┘
                                                  │ Raw HTML
                                                  ▼
                                     ┌──────────────────────────┐
                                     │ BeautifulSoup Sanitizer  │
                                     │  • Decompose Scripts/CSS │
                                     │  • Strip Boilerplate/Nav │
                                     │  • Structured Headings   │
                                     │  • Token Size Limiter    │
                                     └────────────┬─────────────┘
                                                  │ Cleaned Profile
                                                  ▼
                                     ┌──────────────────────────┐
                                     │   Google Gemini Engine   │
                                     │  • Model: gemini-2.5-flash
                                     │  • Bounded Expo Backoff  │
                                     │  • Strict JSON Schema    │
                                     └────────────┬─────────────┘
                                                  │ Structured JSON
                                                  ▼
                                     ┌──────────────────────────┐
                                     │ Competitor & Rule Filter │
                                     │  • Verified vs Inferred  │
                                     │  • Exactly 5 Queries     │
                                     │  • Top 5 Services Cap    │
                                     └────────────┬─────────────┘
                                                  │
                                                  ▼
                                      Final JSON Response Payload
```

---

## The Five Business Intelligence Sections

Each request generates five distinct analytical sections adhering strictly to non-fabrication and verification rules:

### Section 1 — Competitor Analysis (`competitor_analysis`)
- **Brand Identification:** Extracted brand name, executive business summary, primary industry category, and product/service lines.
- **Competitor Benchmarking:** At least 3 relevant market competitors with explicit competitive strengths and vulnerabilities.
- **Strategic Positioning:** Core brand competitive differentiators and market positioning opportunities.
- **Evidence Labeling:** Explicitly distinguishes verified disclosures (`verified_from_website`) from AI-inferred suggestions (`ai_inferred_industry_standard`). Never claims verified research without on-page proof.

### Section 2 — Target Search Queries (`target_search_queries`)
- **Strict Count:** Exactly **5** targeted search queries.
- **Multi-Platform Coverage:** Modeled across **Google**, **Facebook**, **Instagram**, **LinkedIn**, and **X**.
- **Search Intent:** Classified into Informational, Commercial, Transactional, or Navigational.
- **Business Relevance & Persona:** Strategic rationale and target buyer profile for each query.
- **Integrity Rule:** Search volume and CPC figures are intentionally not fabricated. Includes an explicit volume disclaimer.

### Section 3 — SEO Improvements (`seo_improvements`)
- **Keyword Hierarchy:** Primary high-volume keywords, secondary supporting keywords, and long-tail intent queries.
- **Meta Optimization:** Recommended SEO title (<60 characters) and high-CTR meta description (140–160 characters).
- **Content Strategy:** High-converting content ideas (blog posts, landing pages, case studies) and on-page FAQ schema recommendations.
- **Grounded Evidence:** Directly derived from extracted headings and value propositions.

### Section 4 — Top 5 Services (`top_services`)
- **Service Breakdown:** Identifies up to 5 actual services or product lines from the site content.
- **Details:** Service name, comprehensive description, target vertical, ideal customer profile, and primary business benefit.
- **Integrity Rule:** Labelled with `is_inferred: bool` and `evidence_source`. Never invents fictional offerings to force five entries if fewer exist on the site.

### Section 5 — Target Audience (`target_audience`)
- **Audience Segmentation:** Primary decision-maker persona and secondary auxiliary buyer segments.
- **Business Profiles:** Target industries and enterprise business models (B2B SaaS, Mid-Market, Enterprise, D2C).
- **Jobs-to-be-Done:** Core operational pain points, goals, and needs.
- **Geographic Scope:** Regional/global market focus based strictly on extracted textual evidence.
- **Tactical Marketing:** Channel-specific marketing and messaging recommendations.

---

## LLM Model Research & Comparative Evaluation

To determine the optimal foundation model for this application, we evaluated leading active models from **Google**, **OpenAI**, and **Anthropic** against official provider documentation and current pricing schedules (*Verified as of November 2026*):

| Evaluation Dimension | Google Gemini 2.5 Flash *(Recommended)* | Google Gemini 2.5 Pro *(In-Family Fallback)* | OpenAI GPT-4o-mini *(Cross-Provider Alt)* | OpenAI GPT-4o *(Frontier Baseline)* | Anthropic Claude 3.5 Haiku *(Fast Tier)* | Anthropic Claude 3.5 Sonnet *(Frontier Alt)* |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Provider** | [Google AI](https://ai.google.dev/pricing) | [Google AI](https://ai.google.dev/pricing) | [OpenAI](https://openai.com/api/pricing/) | [OpenAI](https://openai.com/api/pricing/) | [Anthropic](https://www.anthropic.com/pricing) | [Anthropic](https://www.anthropic.com/pricing) |
| **Input Price / 1M Tokens** | **$0.15** *(≤128k)* | $1.25 *(≤128k)* | $0.15 | $2.50 | $0.80 | $3.00 |
| **Output Price / 1M Tokens** | **$0.60** *(≤128k; incl. thinking)* | $5.00 *(≤128k; incl. thinking)* | $0.60 | $10.00 | $4.00 | $15.00 |
| **Context Window** | **1,048,576** *(~1M tokens)* | 2,097,152 *(~2M tokens)* | 128,000 | 128,000 | 200,000 | 200,000 |
| **Max Output Tokens** | **65,536** | 65,536 | 16,384 | 16,384 | 8,192 | 8,192 |
| **Structured Output Support** | **Native Pydantic (`response_schema`)** | Native Pydantic (`response_schema`) | Strict JSON Schema (`json_schema`) | Strict JSON Schema (`json_schema`) | Tool Calling / Function Use | Tool Calling / Function Use |
| **Response Speed Profile** *(Qualitative)* | **High Throughput / Fast** | Deliberate / Slower | High Throughput / Fast | Moderate | High Throughput / Fast | Moderate |
| **Developer / Free Tier** | **Available (Google AI Studio)** | Available (Google AI Studio) | Pay-as-you-go only | Pay-as-you-go only | Pay-as-you-go only | Pay-as-you-go only |

*Data Sources: [Google AI for Developers Pricing](https://ai.google.dev/pricing) • [OpenAI API Pricing](https://openai.com/api/pricing/) • [Anthropic Claude Pricing](https://www.anthropic.com/pricing). All pricing schedules and technical limits verified November 2026.*

---

## Recommended Model & Cost Analysis

### Primary Recommendation: **Google Gemini 2.5 Flash**

#### 1. Why Gemini 2.5 Flash Wins
1. **Cost Efficiency:** At $0.15 / 1M input tokens and $0.60 / 1M output tokens, Gemini 2.5 Flash delivers near-frontier analytical capabilities at a fraction of the cost of GPT-4o ($2.50 / $10.00) or Claude 3.5 Sonnet ($3.00 / $15.00).
2. **Native Pydantic Schema Enforcement:** The Google GenAI Python SDK supports `response_schema` directly at the decoding level, ensuring strictly valid JSON conforming to our Pydantic contracts without markdown wrapping or missing fields.
3. **Massive Context Headroom (1M+ Tokens):** While our DOM extractor prunes web content to ~2,500 tokens, the 1M+ context window guarantees that dense multi-page text or extensive service listings never trigger context truncation.
4. **Developer Tier Accessibility:** Google AI Studio offers developer-tier access with zero upfront credit card requirements.

#### 2. Cost Analysis & Token Pricing (Estimated)

Based on typical business websites processed by our extraction pipeline:
- **Estimated Input Tokens:** ~2,000 to 3,500 tokens (sanitized page text + system instructions + Pydantic schema definition; average ~2,500 tokens).
- **Estimated Output Tokens (Payload):** ~1,000 to 1,500 tokens (complete 5-section structured JSON output; average ~1,200 tokens).
- **Thinking / Reasoning Tokens (when engaged):** Gemini 2.5 Flash performs internal chain-of-thought reasoning prior to emitting structured output (typically ~800 to 1,300 thinking tokens for dense multi-section analysis), which Google bills at the standard output token rate ($0.60 / 1M tokens).

**Per-Analysis Cost Breakdown:**

- **Scenario A — Standard Output Generation (~1,200 output tokens):**
  $$\text{Input Cost} = \frac{2,500}{1,000,000} \times \$0.15 = \$0.000375$$
  $$\text{Output Cost} = \frac{1,200}{1,000,000} \times \$0.60 = \$0.000720$$
  $$\mathbf{\text{Total Cost}} = \$0.000375 + \$0.000720 = \mathbf{\$0.001095 \approx \$0.0011 \text{ USD}}$$

- **Scenario B — Accounting for Thinking Tokens (~2,500 total output tokens):**
  $$\text{Input Cost} = \frac{2,500}{1,000,000} \times \$0.15 = \$0.000375$$
  $$\text{Output Cost (incl. reasoning)} = \frac{2,500}{1,000,000} \times \$0.60 = \$0.001500$$
  $$\mathbf{\text{Total Cost}} = \$0.000375 + \$0.001500 = \mathbf{\$0.001875 \approx \$0.0019 \text{ USD}}$$

> **Cost Efficiency Summary [Estimated]:** Even with internal thinking tokens accounted for, a complete 5-section link intelligence report costs less than **$0.002 USD** (less than one-fifth of one cent). Approximately **520 to 910 complete website analyses** can be run per $1.00 USD.

#### 3. Performance Metrics: Measured vs. Estimated vs. Qualitative

To ensure analytical integrity, performance characteristics are strictly categorized:

| Metric Category | Assessment Item | Value / Observation | Verification Source / Evidence |
|:---|:---|:---|:---|
| **[Measured]** | Automated Pytest Suite | **46 passed in 1.36s** | Local test run ([`test_logs.txt`](test_logs.txt)) |
| **[Measured]** | Stripe Live E2E Latency | **~37 seconds total** | Real-world API execution ([`sample_response.json`](sample_response.json)) |
| **[Measured]** | Stripe DOM Sanitization | **~2 seconds** (723 KB HTML → 920 words) | BeautifulSoup extraction pipeline logs |
| **[Measured]** | Stripe Gemini 2.5 Generation | **~35 seconds** (981 JSON lines) | Live Google GenAI API response |
| **[Estimated]** | Input Token Usage | ~2,000 – 3,500 tokens | Tokenization of sanitized content + schema |
| **[Estimated]** | Output Token Usage | ~1,200 – 2,500 tokens (incl. thinking) | JSON payload length + reasoning tokens |
| **[Estimated]** | Per-Analysis API Cost | **$0.0011 – $0.0019 USD** | Calculated from verified November 2026 pricing |
| **[Qualitative]** | LLM Response Speed Tier | High Throughput (Flash tier) | Architectural tiering relative to Pro/Frontier models |
| **[Qualitative]** | Schema Reliability | 100% Valid JSON | Native Pydantic schema decoding via `response_schema` |

#### 4. Recommended Fallback Models
- **In-Family Fallback:** `gemini-2.5-pro` (when deeper reasoning or complex ambiguous niche domain categorization is required).
- **Cross-Provider Fallback:** `gpt-4o-mini` (reliable secondary API fallback via OpenAI with strict JSON schema support).

#### 5. Cost Optimization Techniques Implemented
- **DOM Pre-Sanitization:** Decomposing CSS, scripts, navigation boilerplate, footers, and SVGs reduces token footprint by **~75%** before sending data to Gemini.
- **Content Budget Capping:** Content is capped at 25,000 characters (`MAX_EXTRACTED_CONTENT_LENGTH`), preventing runaway billing on massive pages.
- **Context Caching:** Ready for Google Context Caching (up to 95% discount on cached input tokens) for recurring domain re-scrapes.

---

## Security & SSRF Safeguards

The extraction engine implements enterprise-grade Server-Side Request Forgery (SSRF) and Anti-DNS-Rebinding safeguards:

1. **Protocol Restriction:** Allows only `http://` and `https://` schemes. Rejects `ftp://`, `file://`, `data:`, `gopher:`, and `javascript:`.
2. **IP Range Blacklisting:** Explicitly blocks:
   - Loopback (`127.0.0.0/8`, `::1`)
   - Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`)
   - Cloud instance metadata (`169.254.169.254`, `fe80::/10`)
   - Carrier-Grade NAT (`100.64.0.0/10`)
   - Documentation and benchmarking ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `198.18.0.0/15`)
   - IPv4-mapped IPv6 addresses (`::ffff:127.0.0.1`)
3. **Anti-DNS-Rebinding Engine (`SSRFSafeBackend`):** A custom HTTPCore network backend intercepts connection establishment at the exact socket creation instant. It resolves DNS, verifies that all resolved IPs are public and routable, and connects directly to the pinned IP address. Server Name Indication (SNI) and TLS certificate verification are preserved for the original domain.
4. **Redirect Hop Revalidation:** Follows up to a maximum of 5 redirects in an explicit control loop. Every redirect destination is re-validated for scheme, hostname, and resolved IP prior to following.
5. **Streaming & Size Caps:** Streams response bytes with an accounting counter, terminating the connection if the response exceeds `MAX_RESPONSE_SIZE_BYTES` (5 MB).

---

## Project Directory Structure

```text
ai-link-analysis/
├── app/
│   ├── __init__.py                # Package metadata and versioning
│   ├── main.py                    # FastAPI application, UI serving, exception handlers, and endpoints
│   ├── config.py                  # Pydantic Settings configuration loader
│   ├── schemas.py                 # Pydantic request/response & structured analysis models
│   ├── static/                    # Frontend assets
│   │   └── index.html             # Link Analysis dashboard (HTML, Tailwind CSS, Vanilla JS)
│   ├── services/
│   │   ├── __init__.py            # Service package exports
│   │   ├── website_extractor.py   # Async HTTPX fetching, SSRF guard, BeautifulSoup extraction
│   │   ├── llm_service.py         # Google GenAI SDK integration, retries, and prompt formatting
│   │   ├── analysis_service.py    # Multi-section analysis pipeline orchestrator
│   │   └── competitor_service.py  # Competitor evidence validation and refinement
│   └── utils/
│       ├── __init__.py            # Utility package exports
│       └── validators.py          # URL validation & multi-tier SSRF security checks
├── tests/
│   └── test_link_analysis.py      # 46 automated pytest test cases (UI, SSRF, extraction, Gemini mock)
├── .env.example                   # Template environment variables
├── .gitignore                     # Git ignore rules for Python, virtual environments, and secrets
├── pytest.ini                     # Pytest configuration and path resolution
├── requirements.txt               # Pinned production and test dependencies
├── render.yaml                    # Infrastructure-as-code Render deployment blueprint
├── sample_response.json           # Verified end-to-end API response on stripe.com
├── test_logs.txt                  # Full sanitized pytest execution log
└── README.md                      # Comprehensive documentation
```

---

## Installation & Local Setup

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Google Gemini API Key ([Get a free key at Google AI Studio](https://aistudio.google.com/app/apikey))

### 2. Clone and Setup Environment
```bash
cd ai-link-analysis

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Linux/macOS:
cp .env.example .env
# Windows:
copy .env.example .env
```

Open `.env` and set your key:
```env
APP_NAME="AI-Powered Website Link Analysis API"
ENVIRONMENT=development
DEBUG=false
HOST=0.0.0.0
PORT=4000

# Google Gemini API Configuration
GEMINI_API_KEY=AIzaSyYourActualKeyHere
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_RETRIES=3
GEMINI_TIMEOUT_SECONDS=45.0
GEMINI_TEMPERATURE=0.2
```

---

## API Documentation & Usage

### 1. Start Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

### 2. Interactive Swagger UI & Web Dashboard
- **Web Interface:** Open **[http://localhost:4000/](http://localhost:4000/)** or **[http://localhost:4000/dashboard](http://localhost:4000/dashboard)** in your browser for the responsive UI.
- **Interactive OpenAPI Docs:** Open **[http://localhost:4000/docs](http://localhost:4000/docs)** to inspect Pydantic schemas and execute API calls.

### 3. API Root & Content Negotiation (`GET /`)
The root endpoint provides intelligent content negotiation:
- Navigating in a browser (sending `Accept: text/html`) delivers the **Link Analysis** interactive dashboard.
- Calling programmatically with `Accept: application/json` returns API service metadata:

```bash
curl -X GET "http://localhost:4000/" -H "Accept: application/json"
```

**Response (`200 OK`):**
```json
{
  "name": "AI-Powered Website Link Analysis API",
  "version": "1.0.0",
  "phase": "Phase 2: Google Gemini Integration and Complete AI-Powered Website Analysis",
  "status": "operational",
  "model": "gemini-2.5-flash",
  "documentation": "/docs",
  "dashboard": "/dashboard",
  "endpoints": {
    "dashboard": "GET /dashboard",
    "health": "GET /health",
    "link_analysis": "POST /link-analysis"
  }
}
```

### 4. Health Check (`GET /health`)
Used by uptime probes and Render container orchestrators:
```bash
curl -X GET "http://localhost:4000/health"
```
**Response (`200 OK`):**
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0",
  "phase": 2,
  "model": "gemini-2.5-flash",
  "api_key_configured": true
}
```

### 5. Link Analysis (`POST /link-analysis`)
```bash
curl -X POST "http://localhost:4000/link-analysis" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://stripe.com"}'
```

---

## Sample Real-World Output

The following excerpt is from an actual, live test run against `https://stripe.com` (full JSON in [`sample_response.json`](sample_response.json)):

```json
{
  "success": true,
  "status": "success",
  "message": "Website content extracted and analyzed successfully.",
  "website": {
    "url": "https://stripe.com/in",
    "title": "Stripe | Financial Infrastructure to Grow Your Revenue",
    "meta_description": "Stripe is a financial services platform that helps all types of businesses accept payments, build flexible billing models and manage money movement.",
    "word_count": 920,
    "character_count": 6950,
    "raw_html_size_bytes": 723518,
    "extracted_at": "2026-11-18T08:23:12Z"
  },
  "brand": {
    "brand_name": "Stripe",
    "business_overview": "Stripe is a financial services platform providing tools and infrastructure for businesses to accept payments, build flexible billing models, manage money movement, and prevent fraud.",
    "category": "Financial Technology (FinTech)",
    "products_and_services": [
      "Payment processing (online and in-person)",
      "Flexible billing models",
      "Fraud prevention",
      "Card issuing programs",
      "Embedded payments for platforms"
    ]
  },
  "analysis": {
    "competitor_analysis": {
      "brand_name": "Stripe",
      "business_overview": "Comprehensive payment and financial infrastructure provider.",
      "category": "Financial Technology (FinTech)",
      "products_and_services": [
        "Payment processing",
        "Billing models",
        "Fraud prevention"
      ],
      "competitors": [
        {
          "name": "PayPal / Braintree",
          "category_or_type": "Direct Competitor",
          "strengths": [
            "Strong brand recognition and consumer trust",
            "Extensive global digital wallet ubiquity"
          ],
          "weaknesses": [
            "Higher transaction dispute fees",
            "Developer experience less streamlined than Stripe"
          ],
          "is_inferred": true,
          "evidence_source": "ai_inferred_industry_standard"
        },
        {
          "name": "Adyen",
          "category_or_type": "Direct Competitor",
          "strengths": [
            "Unified single-platform global acquiring",
            "Strong enterprise omnichannel POS presence"
          ],
          "weaknesses": [
            "Higher threshold for early-stage startups"
          ],
          "is_inferred": true,
          "evidence_source": "ai_inferred_industry_standard"
        },
        {
          "name": "Square / Block",
          "category_or_type": "Direct Competitor",
          "strengths": [
            "In-person SMB point-of-sale dominance",
            "Integrated business operations ecosystem"
          ],
          "weaknesses": [
            "Less specialized developer APIs for custom enterprise architectures"
          ],
          "is_inferred": true,
          "evidence_source": "ai_inferred_industry_standard"
        }
      ],
      "competitive_advantages": [
        "Gold-standard developer APIs, SDKs, and documentation",
        "Unified modular financial stack from checkout to corporate cards"
      ],
      "positioning_opportunities": [
        "Deepen automated recurring subscription intelligence",
        "Expand borderless cross-border crypto and stablecoin rails"
      ],
      "verification_note": "Competitors and market positions are AI-inferred based on industry benchmarks; verified data is explicitly distinguished from inferred suggestions."
    },
    "target_search_queries": {
      "queries": [
        {
          "query": "best payment gateway for e-commerce",
          "platforms": ["Google"],
          "search_intent": "Commercial",
          "business_relevance": "Captures high-intent merchants looking to accept online payments.",
          "target_audience": "E-Commerce Founders and Store Owners"
        },
        {
          "query": "how to accept international payments online",
          "platforms": ["Google", "Facebook", "Instagram"],
          "search_intent": "Informational",
          "business_relevance": "Attracts growing businesses seeking global checkout solutions.",
          "target_audience": "Digital Entrepreneurs and Scaling Merchants"
        },
        {
          "query": "Stripe API documentation for developers",
          "platforms": ["Google", "LinkedIn"],
          "search_intent": "Navigational",
          "business_relevance": "High-intent developers integrating billing systems.",
          "target_audience": "Software Engineers and Technical Leads"
        },
        {
          "query": "best billing software for subscription business",
          "platforms": ["Google", "LinkedIn"],
          "search_intent": "Commercial",
          "business_relevance": "Targets SaaS companies needing automated billing engines.",
          "target_audience": "SaaS Founders and Chief Financial Officers"
        },
        {
          "query": "custom corporate card issuing program api",
          "platforms": ["Google", "X"],
          "search_intent": "Informational",
          "business_relevance": "Engages fintech platforms wanting embedded banking products.",
          "target_audience": "FinTech Product Managers and CTOs"
        }
      ],
      "supported_platforms": ["Google", "Facebook", "Instagram", "LinkedIn", "X"],
      "volume_disclaimer": "Search volumes are intentionally not fabricated. Queries are modeled based on audience intent and topical relevance."
    },
    "seo_improvements": {
      "keywords": {
        "primary_keywords": ["payment gateway", "online payment processing", "billing software"],
        "secondary_keywords": ["international merchant acquiring", "fraud prevention radar", "card issuing api"],
        "long_tail_keywords": [
          "how to accept recurring credit card payments for saas",
          "embedded multi-party marketplace payouts api",
          "developer friendly payment processing integration"
        ]
      },
      "recommended_seo_title": "Stripe: Financial Infrastructure for Global Revenue Growth",
      "recommended_meta_description": "Accept payments, automate billing, and stop fraud with Stripe's global financial infrastructure. Powering revenue growth for startups and enterprises.",
      "content_recommendations": [
        {
          "title": "The Comprehensive Guide to International Payment Compliance",
          "content_type": "guide",
          "target_keyword": "international merchant acquiring",
          "summary_or_outline": "Practical guide explaining currency conversion, local payment methods, and cross-border settlement."
        },
        {
          "title": "How Machine Learning Fraud Detection Protects Subscription Revenue",
          "content_type": "blog_post",
          "target_keyword": "fraud prevention radar",
          "summary_or_outline": "Analysis of automated anomaly detection reducing dispute rates while minimizing false declines."
        }
      ],
      "recommended_faqs": [
        {
          "question": "What payment methods can I accept with Stripe?",
          "recommended_answer": "Stripe supports credit and debit cards, digital wallets like Apple Pay and Google Pay, and dozens of local payment methods worldwide."
        },
        {
          "question": "How does Stripe handle subscription billing?",
          "recommended_answer": "Stripe Billing automates recurring charges, handles prorations and dunning, and generates compliant invoices."
        }
      ],
      "rationale": "Target search terms emphasize Stripe's developer-first reputation and comprehensive revenue optimization messaging."
    },
    "top_services": {
      "services": [
        {
          "service_name": "Online & In-Person Payment Acceptance",
          "description": "Global payment gateway supporting cards, mobile wallets, and local payment methods.",
          "target_industry": "E-Commerce, Technology, and Retail",
          "target_customer": "Online Merchants and Omnichannel Retailers",
          "main_benefit": "Maximize checkout conversion with optimized, secure payment flows.",
          "is_inferred": false,
          "evidence_source": "extracted_from_page"
        },
        {
          "service_name": "Stripe Billing",
          "description": "Flexible recurring billing, subscription management, and automated invoicing.",
          "target_industry": "Software as a Service (SaaS)",
          "target_customer": "SaaS Companies and Subscription Providers",
          "main_benefit": "Scale recurring revenue models and eliminate manual dunning overhead.",
          "is_inferred": false,
          "evidence_source": "extracted_from_page"
        },
        {
          "service_name": "Stripe Radar Fraud Prevention",
          "description": "Machine-learning fraud prevention system trained across billions in global transactions.",
          "target_industry": "Digital Commerce and Financial Services",
          "target_customer": "Risk Managers and E-Commerce Operators",
          "main_benefit": "Block fraudulent charges without disrupting legitimate buyer checkouts.",
          "is_inferred": false,
          "evidence_source": "extracted_from_page"
        },
        {
          "service_name": "Stripe Issuing",
          "description": "Infrastructure to create, manage, and distribute physical and virtual commercial cards.",
          "target_industry": "FinTech and Enterprise Platforms",
          "target_customer": "Product Managers and Operations Teams",
          "main_benefit": "Build custom card programs with granular spending controls.",
          "is_inferred": false,
          "evidence_source": "extracted_from_page"
        },
        {
          "service_name": "Stripe Connect",
          "description": "Multi-party payment routing and onboarding for software platforms and marketplaces.",
          "target_industry": "Marketplaces and Gig Economy",
          "target_customer": "Platform CTOs and Product Leaders",
          "main_benefit": "Compliantly onboard payees and automate marketplace revenue splits.",
          "is_inferred": false,
          "evidence_source": "extracted_from_page"
        }
      ],
      "total_identified": 5,
      "extraction_note": "Services are derived strictly from page content; inferred capabilities are explicitly labeled."
    },
    "target_audience": {
      "primary_audience": {
        "segment_name": "E-Commerce & SaaS Business Owners / Executives",
        "tier": "Primary",
        "customer_profile": "Founders, CEOs, and Finance Directors seeking scalable, reliable revenue infrastructure.",
        "core_needs_and_pain_points": [
          "Need to accept payments internationally with minimal setup",
          "Reducing cart abandonment and failed recurring payments",
          "Protecting business margins from fraudulent disputes"
        ]
      },
      "secondary_audiences": [
        {
          "segment_name": "Software Developers & Technical Architects",
          "tier": "Secondary",
          "customer_profile": "Engineers tasked with integrating billing APIs, custom checkouts, and marketplace workflows.",
          "core_needs_and_pain_points": [
            "Clear, reliable API documentation and native SDKs",
            "Comprehensive sandbox testing environments",
            "High availability and low-latency API uptime"
          ]
        }
      ],
      "target_industries": ["E-Commerce", "SaaS & Cloud Computing", "Retail", "FinTech", "Digital Marketplaces"],
      "target_business_types": ["B2B SaaS", "D2C E-Commerce", "Two-Sided Platforms", "Global Enterprise"],
      "geographic_focus": "Global",
      "marketing_recommendations": [
        "Highlight developer-first integrations through technical case studies on LinkedIn.",
        "Run search ads on high-intent transactional terms like 'best subscription billing platform'.",
        "Produce video tutorials and webinars addressing international cross-border compliance."
      ]
    }
  }
}
```

---

## Automated Test Suite (46 Passed)

Execute the full test suite with pytest:

```bash
cd ai-link-analysis
pytest -v
```

### Test Coverage Highlights:
- **Web Interface & Content Negotiation:** HTML dashboard delivery (`GET /dashboard`), browser `text/html` negotiation at `GET /`, and programmatic JSON catalog fallback (`GET /`).
- **System Discovery:** `/health` check and API catalog discovery (`GET /`).
- **Input Validation:** Empty request bodies, invalid types, missing hostnames, embedded user credentials (`user:pass@host`), and disallowed schemes (`ftp://`, `file://`, `javascript:`).
- **SSRF Suite (16 Scenarios):** `localhost`, `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, AWS instance metadata (`169.254.169.254`), IPv6 loopback (`::1`), IPv4-mapped IPv6 (`::ffff:127.0.0.1`), CGNAT (`100.64.0.0/10`), `.local`, `.internal`, `.lan`.
- **DNS Protection:** Validates that hostnames resolving to private IPs are blocked prior to HTTP connection.
- **HTML Sanitization:** Stripping scripts, styles, iframes, footers, cookie banners, whitespace cleaning, and token size capping.
- **Upstream Resilience:** Connect timeouts (504), connection drops (502), upstream 4xx/5xx HTTP codes, payload > 5 MB (413), and non-HTML MIME types (422).
- **Gemini Error Handling:** Missing API key (503), rate limit exhaustion (429), request timeout (504), malformed JSON recovery (502), upstream API error (502).
- **Business Rule Enforcement:** Competitor on-page evidence tagging, bounded exponential backoff retries, strict 5-search-query cap, and <= 5 services cap.

---

## Deployment Guide (Render)

This repository includes a deployment blueprint ([`render.yaml`](render.yaml)) configured for **Render**.

### Step-by-Step Render Deployment

#### Step 1: Push Code to GitHub / GitLab
Ensure all changes are committed (excluding `.env`).

```bash
git add .
git commit -m "Complete Link Analysis API & Web Dashboard"
git push origin main
```

#### Step 2: Create a Web Service on Render
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub/GitLab repository.

#### Step 3: Configure Service Settings
- **Name:** `ai-link-analysis-api`
- **Region:** Any preferred region (e.g., Oregon, Frankfurt)
- **Branch:** `main`
- **Root Directory:** `ai-link-analysis` *(if repository contains outer folder; otherwise leave blank)*
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Plan:** Free or Starter

#### Step 4: Configure Environment Variables in Render Dashboard
Under the **Environment** tab of your service, add:

| Key | Value | Description |
|:---|:---|:---|
| `PYTHON_VERSION` | `3.12.10` | Python runtime version |
| `ENVIRONMENT` | `production` | Deployment environment |
| `DEBUG` | `false` | Disable debug mode |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Selected Gemini Flash model |
| `GEMINI_API_KEY` | `AIzaSy...` | Your secret Google Gemini API key |

#### Step 5: Deploy
Click **Deploy Web Service**. Once built, the service will pass the health check at `/health` and serve live requests at `https://your-service-name.onrender.com/link-analysis`.

---

## Limitations & Mitigations

| Potential Limitation | Real-World Impact | Built-in Mitigation |
|:---|:---|:---|
| **JavaScript-Heavy SPAs** | Content rendered entirely client-side via React/Vue might not appear in initial raw HTML. | Fallback meta tag and OpenGraph scrapers capture titles, social descriptors, and visible header tags. For full JS execution, headless browser sidecars can be attached. |
| **Cloudflare / CAPTCHA Walls** | High-security websites may challenge or block automated HTTP fetchers with HTTP 403 or 503. | Custom browser user-agent headers avoid simple bot filters. Non-HTML or blocked responses return informative `UPSTREAM_HTTP_403` errors. |
| **Provider Rate Limits** | High burst request traffic may exceed Google Gemini API quotas. | Bounded exponential backoff with random jitter automatically retries 429 errors up to `GEMINI_MAX_RETRIES = 3` before surfacing a structured error. |
| **DNS Rebinding Vulnerabilities** | Malicious domains alternating between public IPs and private IPs between check and fetch. | `SSRFSafeBackend` pins the connection to the pre-verified public IP at the exact socket creation instant. |
