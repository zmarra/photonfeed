# Architecture

## Multi-agent pipeline

Why multi-agent (vs. one big prompt): the task naturally factors into stages with
different prompts, models, and tools. Triage wants a cheap embedding + small reranker;
the critic wants a smart model with web-search; the connector needs DB access. Doing
this as one prompt would be slow, expensive, and lower quality.

### Ingestion (per-user, one-time + on upload)

```
PDF file
  ↓
pypdf → text + page-level metadata
  ↓
metadata-extractor agent → title, authors, year, abstract, DOI
  ↓
GROBID → structured reference list
  ↓
embed (title + abstract) → store in papers table with weight label:
    - own:        ×3.0
    - citing-me:  ×3.0
    - library:    ×1.0
  ↓
profile-builder → weighted centroid of embeddings → user.profile_vector
```

### Daily pipeline (cron, ~nightly)

```
Source agents (parallel)
  ├─ arXiv physics.optics
  └─ arXiv physics.app-ph
       ↓ (dedup, ~150 candidates/day)
Triage agent
  step 1: cosine sim to profile_vector → top-50
  step 2: Claude small model rerank with profile keywords → top-10
       ↓
Per-candidate (fan-out, parallel):
  ├─ Summarizer  → TL;DR, 3-bullet
  ├─ Critic      → novelty, claim support, what's missing
  └─ Connector   → links to user's library refs by similarity + LLM judgment
       ↓ (fan-in)
Editor agent → composes today's feed entry (markdown)
       ↓
Write to feed_items table
```

### Feedback loop (nightly)

```
thumbs_events → label embeddings (up=+1, down=-1)
       ↓
gradient update on profile_vector (small step size + decay)
       ↓
write profile_vector_version row for traceability
```

## Data model (sketch)

- `papers` — universal paper records (own, library, arXiv-fetched)
- `paper_weights` — per-source weight (3.0 / 1.0)
- `paper_refs` — citation edges extracted via GROBID
- `users` — single row in v0.1
- `user_profiles` — versioned profile vectors
- `feed_items` — daily feed entries with summary / critique / connections
- `feedback_events` — thumbs with paper + timestamp

## Open questions

- Should the critic agent be allowed web search? (More accurate; slower; cost)
- Embedding model: Voyage `voyage-3-large` (best for sci) vs OpenAI `text-embedding-3-large`
- Reference matching: pure cosine on embedded titles, or do we need a name-based join too?
