# Getting Your Free API Keys

Verified against official sources on 2026-07-11 (see Sources at the bottom). Where official docs didn't publish a specific number, that's noted rather than guessed.

## 1. Mistral API key (La Plateforme)

1. Go to **console.mistral.ai** and create an account (or sign in).
2. Once logged in, the account defaults to **Free mode** — Mistral's docs describe this as "the lowest limits, intended for evaluation and prototyping," giving rate-limited access to all models (including Mistral Small/Medium/Large and Codestral) at $0.
3. Go to **API Keys** in the console and generate a key. Save it somewhere safe — you'll paste it into `mistralBot`'s first-run prompt.
4. To see your account's exact current rate limits (requests/sec, tokens/min, tokens/month), check **Admin Console → Limits** (`admin.mistral.ai/plateforme/limits`) after signing in — official docs don't publish one fixed number, it's tier-dependent.

**Things I could confirm from Mistral's own docs:**
- Free mode exists by default and is rate-limited (docs.mistral.ai).
- Exact limits are account-specific and shown in the Admin Console, not published as a fixed number.

**Things reported consistently by third-party sources but not stated on Mistral's own pricing/docs pages I could fetch** — worth confirming yourself at sign-up since I can't verify them against a primary source:
- Some report phone verification is required, others say it isn't; card is not required either way per every source I checked.
- A commonly cited (unofficial) ballpark: ~1 request/sec and up to ~1 billion tokens/month on free mode.
- Free-tier requests may be used to improve Mistral's models (i.e., no data-isolation guarantee) — if that matters to you, check the current data-usage terms in the console before sending sensitive prompts.

## 2. Web search API key — now using Tavily instead of Brave

We originally planned to use Brave Search, but verification turned up that Brave requires a credit card on file even for its free tier (see comparison table below). We're switching to **Tavily**, which needs no card and is purpose-built for feeding LLMs like Mistral.

See the "Decision: switching to Tavily" section below for signup steps.

## Search provider comparison (all re-verified against each vendor's own docs)

| Provider | Free allowance | Recurs monthly? | Credit card required? | Notes |
|---|---|---|---|---|
| Brave Search API | $5 credit/mo (~1,000 queries) | Yes | **Yes** | Raw web results |
| Tavily | 1,000 credits/mo | Yes | **No** | Purpose-built for LLM grounding; returns pre-summarized snippets, which is a good fit for feeding straight into Mistral |
| Serper.dev | 2,500 queries | **No — one-time trial, credits expire after 6 months** | No | Real Google SERP data, but not sustainable for ongoing free use once the trial runs out |
| DuckDuckGo scraping | Unlimited | N/A | No | No signup at all, but unofficial/fragile — breaks if DuckDuckGo changes their HTML, and results are less structured |

## Decision: switching to Tavily
Given no-card-required and a recurring (not one-time) monthly allowance, **Tavily** is the best match for the "completely free" goal — better than Brave (needs a card) and Serper (one-time trial only). Updating the spec accordingly:

### Tavily signup steps
1. Go to **tavily.com** and sign up with email or Google/GitHub OAuth — no credit card needed.
2. Your dashboard shows an API key immediately (starts with `tvly-`) — copy it for `mistralBot`'s first-run prompt.
3. Free tier: 1,000 API credits/month, recurring. Beyond that it's pay-as-you-go at $0.008/credit if you ever choose to add a card — not required to keep using the free allowance.

## Sources
- [Mistral pricing](https://mistral.ai/pricing/)
- [Mistral API pricing](https://mistral.ai/pricing/api)
- [Rate limits and usage tiers — Mistral Docs](https://docs.mistral.ai/deployment/ai-studio/tier)
- [Why am I hitting API rate limits — Mistral Help Center](https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them)
- [Brave Search API pricing](https://api-dashboard.search.brave.com/documentation/pricing)
- [Brave Search API quickstart](https://api-dashboard.search.brave.com/documentation/quickstart)
