# Scraping Prompt Limit Policy

## Overview

This document explains the prompt-limit work implemented to control scraping prompt volume across all scraping categories and reduce rate-limit failures when using free-tier LLM API keys.

The change was designed to solve two practical issues:

1. Prompt progress and execution behavior should be consistent across all categories (not just events).
2. Prompt volume should be bounded so users do not accidentally exceed free-tier LLM quotas during scraping runs.

## What Was Implemented

### 1. Global per-category prompt cap

A shared maximum number of active prompts per category is now enforced system-wide.

- New setting: `PROMPT_MAX_ACTIVE_PER_CATEGORY`
- Env var: `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY`
- Default fallback behavior:
  - If explicit env var is set, use it.
  - Otherwise, fallback to `GEMINI_SCRAPING_MAX_RPD`.
  - If neither is available, fallback to `20`.
- Safety bounds are applied in code to keep values in a safe range.

This gives a quota-aware default for free-tier usage while still allowing manual override.

### 2. Runtime enforcement in all category scrapers

All category scrapers read prompt queries through the shared method in `BaseScraper`.

That method now enforces the global max prompt cap for active prompts returned to scrapers.

This applies consistently to all categories that use shared prompt loading:

- events
- news
- tools
- corpus
- courses
- opportunities

Result: run progress and search execution now reflect the same policy everywhere.

### 3. API-side enforcement when adding/reactivating prompts

Prompt management endpoints now enforce the cap before activating additional prompts.

Behavior when cap is reached:

- Add new active prompt: rejected with HTTP 400.
- Reactivate an existing inactive prompt: rejected with HTTP 400.
- Keep existing active prompt unchanged: allowed.

Response payload includes details to help UI and users understand the limit:

- `max_active_prompts`
- `active_count`
- clear error message indicating category and usage

### 4. Prompt generation endpoint aware of remaining slots

Generated prompt suggestions are now constrained by remaining capacity.

If category usage is full:

- prompt generation returns HTTP 400 with limit metadata

If there is remaining capacity:

- generated prompts are truncated to available slots

This prevents suggesting prompts users cannot save.

### 5. Category dashboard UI updates

The category dashboard was updated to expose and enforce this policy in the interface.

#### Server-rendered metadata

The dashboard context now includes:

- `max_active_prompts`
- `active_prompt_count`
- `prompt_slots_remaining`

These are embedded as data attributes in the prompt composer.

#### UX behavior

- Prompt help text now shows usage: `current/max used`.
- Add prompt action is blocked client-side when cap is reached.
- Add from generated suggestions is blocked when cap is reached.
- Add all suggestions stops when the cap is reached.
- User-facing feedback explains when the maximum is reached.

## Why This Design

### Why not unlimited prompts?

Unlimited active prompts can trigger excessive search/extraction workload and quickly hit free-tier LLM quota limits, especially in categories that perform LLM extraction after web search.

### Why cap in both API and UI?

- UI-only checks are bypassable.
- API-only checks are safe but less user-friendly.

Using both gives strong safety plus clear UX.

### Why tie default to `GEMINI_SCRAPING_MAX_RPD`?

It makes the default prompt policy quota-aware for environments where Gemini free-tier daily limits are already configured. Teams can still set a stricter or looser explicit cap with `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY`.

## Files Changed

Main files involved in this implementation:

- `scraping/scraping_settings.py`
- `scraping/scrapers/base.py`
- `scraping/views_root.py`
- `templates/scraping/category_dashboard.html`
- `scraping/test_prompt_management.py`

Contextual related file (previous events-only behavior adjustment):

- `scraping/scrapers/events.py`

## Detailed Behavior Reference

### Effective max prompt limit calculation

Effective max is determined in this order:

1. `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY`
2. `GEMINI_SCRAPING_MAX_RPD`
3. hard fallback `20`

Then bounded for safety in code.

### Add prompt API behavior

When creating a new active prompt or reactivating an inactive one:

- If `active_count >= max_active_prompts`: reject with HTTP 400.
- Else: allow and return updated metadata.

### Scraper query loading behavior

At runtime, active queries loaded from DB are clipped to the effective max.

This guarantees backend consistency even if unexpected data exists.

## Test Coverage Added

Tests were added/updated in `scraping/test_prompt_management.py` to verify:

1. API rejects prompt additions when category cap is reached.
2. Category dashboard contains max and active prompt metadata.

Existing prompt management tests remain valid and continue covering baseline behavior.

## Operations and Configuration Guide

### Recommended settings for free-tier usage

If you are using a free LLM key, start with a conservative cap:

- `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY=10` (very safe)
- `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY=15` (balanced)
- `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY=20` (higher throughput)

### Where to set

Set environment variable in your deployment/runtime config where scraping services run.

Examples:

- local `.env`
- Docker compose environment section
- CI/CD environment variables

### Tuning strategy

1. Start with a conservative cap.
2. Observe rate-limit errors over several runs.
3. Increase cap gradually if no quota pressure is observed.
4. Lower cap if rate-limit errors increase.

## Known Constraints

- This implementation does not perform live quota probing against provider APIs.
- It enforces a policy-based cap driven by configured quota values.
- Provider-side quotas can still change independently of local config.

## Rollback Plan

If you need to relax policy quickly:

1. Set `SCRAPING_PROMPT_MAX_ACTIVE_PER_CATEGORY` to a higher value.
2. Redeploy/restart services.

If you need to disable practical enforcement effect:

- Use a very high cap value (not recommended for free-tier keys).

## Summary

The prompt-limit policy is now centralized, quota-aware, and enforced consistently across all scraping categories at runtime, API, and UI levels. It prevents uncontrolled prompt growth, improves predictability of scraping runs, and reduces rate-limit risk for free-tier LLM usage.
