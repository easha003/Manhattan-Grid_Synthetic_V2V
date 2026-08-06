# 2026-08-06 — the single-lane two-way campaign, superseded by one-way

Nine traces, `lanes_per_direction: 1`, both directions sharing each street,
90 s signal cycle, 5–40 m tagged-pair window. Config hash `92bf9cb5`, produced
by commit `d165358`.

Superseded by the one-way two-lane campaign: every street now runs a single
direction with two lanes, the cycle is 45 s, and the pair window is 5–100 m.
That conversion is the point rather than a detail — the single-lane layout made
same-lane blockage impossible by construction, which held mid-block V-VLC
unavailability at 0.38% and removed the only impairment a road map cannot
predict. It is 5.9–7.4% on the replacement.

Vehicle state is not kept, matching the convention of the three earlier
archives: manifests, routes, signals and extracted pairs only. These traces
cannot be re-analysed, only read for provenance. They are reproducible from the
recorded config hash and commit.
