---
name: Faking a smooth price move on a time-based chart
description: Why smoothing a manual price jump by reshaping recent price *values* still looked like a vertical line, and what actually fixed it.
---

When a chart plots price vs. real timestamp (not vs. point index), a manual
price adjustment that only edits the *price* field of the last few history
points is not enough to make it look organic. If those recent points'
timestamps are clustered close together in real wall-clock time (e.g. because
a human tester ran the command a few times within minutes, faster than the
normal update cadence, or because an earlier flawed fix inserted several
points seconds apart), then no amount of reshaping the *values* changes how
compressed they look on a 24h-wide time axis — it still renders as a single
near-vertical segment.

**Why:** two earlier fix attempts failed for this reason: one spread new
points across ~25 seconds (invisible against a 24h axis), the other reshaped
the last N *existing* points' prices but left their already-clustered
timestamps untouched.

**How to apply:** to make a manual value change look like several normal
ticks on a time-based chart, fabricate a synthetic timestamp window spanning
several real tick-intervals (e.g. steps × normal-update-interval, with
jitter), discard/replace whatever points already exist inside that window
regardless of their original timestamps, and interpolate the value across the
new evenly-spaced-with-jitter timestamps ending exactly at "now" with the
target value. Build the gaps as a strictly-increasing cumulative sum (not
independent per-point random offsets) so jitter can never invert the
ordering.
