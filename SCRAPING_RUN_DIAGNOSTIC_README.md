# Scraping Run Diagnostics

This note explains why a scraping run can appear to finish with `0 created` and `0 skipped`, and why that is usually not an LLM-translation problem.

## Short answer

The scraper does not only create new rows. It can also update existing ones.

So a run may have:

- `items_created = 0`
- `items_skipped = 0`
- `items_updated > 0`

In that case the run did real work, but the old notification text made it look empty because it only mentioned created and skipped counts.

The current notification message now includes updated items too.

## What the counters mean

The scraping pipeline tracks three separate outcomes:

- `created`: a brand new database row was inserted.
- `updated`: an existing row matched and was refreshed.
- `skipped`: the candidate was rejected before save.

If the same event is found again, the code often treats it as an update instead of a new insert. That is expected behavior, not a failure.

## Where the confusion came from

The run-complete notification used to say only:

- created
- skipped

It did not show `updated`.

That meant a run that mostly updated existing rows could still display:

- `0 created`
- `0 skipped`

even though items were actually processed and updated.

## Is the LLM validation too strict?

Not in the way you were describing.

The save decision is not based on Arabic translation quality alone. The pipeline uses several layers:

1. LLM extraction and normalization.
2. Validation rules for required fields, URLs, relevance, and event structure.
3. A confidence threshold.
4. Duplicate detection and upsert logic.

So when a run yields no new inserts, the reason is usually one of these:

- the item was rejected by validation,
- the item was considered too low-confidence,
- the item matched an existing record and was updated,
- or the source produced very similar candidates repeatedly.

## What actually drives confidence now

Arabic translation is no longer used as a confidence cap in the main scoring path.

Current scoring is based on validation and completeness signals such as:

- title presence and length,
- description presence,
- start date,
- source URL or website,
- event relevance and event-like signals.

The previous Arabic-translation cap was removed from the scoring path, so translation status should not be the reason the score collapses to zero.

## What still uses Arabic translation

Arabic translation still exists for moderation and metadata.

That means:

- pending items can still be translated manually by the admin,
- translation status is still stored,
- admin review views can still show translation context.

But translation status should not block or dominate the core confidence score anymore.

## Event deduplication behavior

For events, the scraper uses an upsert pattern based on the event title and start date.

That means:

- same title + same date often becomes an update,
- slight variants of the same event can still collapse into the same row,
- repeated runs over the same source often produce more updates than creates.

This is the main reason you can see low create counts even when the scraper is working correctly.

## Validation gates that can still reject items

An event candidate can still be skipped if it fails hard rules such as:

- missing or invalid title,
- generic listing-like title,
- missing or invalid start date,
- date too old or too far in the future,
- missing website,
- blocked source host,
- irrelevant topic,
- missing event signal words,
- low LLM confidence.

So the system is not just checking the LLM score. It is also checking whether the item looks like a real event and whether it is worth saving.

## Why you may still see `0 created / 0 skipped`

The most common reasons are:

1. The run updated existing records only.
2. The notification you are looking at is from the old summary format.
3. The scraper returned very few candidates and all of them matched existing rows.
4. The candidates were rejected before persistence, but the summary you saw did not include the rejection detail.

## What to inspect when this happens

Check these values in the run record or logs:

- `items_created`
- `items_updated`
- `items_skipped`
- `items_found`
- `errors`

For events, also check:

- whether the event already exists with the same title and start date,
- whether the candidate failed the hard validation rules,
- whether the source produced listing pages instead of actual event pages,
- whether the confidence stayed below the save threshold.

## Practical interpretation

If the scraper says `0 created` but `items_updated` is greater than zero, the scraper is not broken. It is reusing existing rows.

If all three are zero, then the issue is usually upstream extraction or validation, not Arabic translation.

## Current conclusion

The old `0 created / 0 skipped` message was misleading because it hid updates.

The actual system behavior is:

- Arabic translation is not the main confidence driver anymore.
- Validation and deduplication are the real filters.
- Updates are normal and should be counted separately.

If you want a run to show useful progress, the dashboard and notifications must always show `created`, `updated`, and `skipped` together.