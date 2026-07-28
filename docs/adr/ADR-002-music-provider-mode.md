# ADR-002: Music provider mode — `direct`, YouTube primary

- **Status:** Accepted
- **Decided:** 2026-07-21 (Phase 0 §0.4, `PROV-POC-001…011`)
- **Recorded:** 2026-07-28 — see "Why this file is late" below
- **Amended:** 2026-07-26 (Spotify's role revised; the mode itself unchanged)
- **Phase / tasks:** Phase 0 §0.4, Phase 5 §5.1 `PROV-001…006`, §5.3 `YT-001…006`, §5.6 `SPOT-001…004`
- **Relates to:** ADR-001 (architecture boundaries), ADR-005 (n8n deployment mode)

## Context

Melody needs a music provider for four operations: **search**, **taste import**,
**playlist writes**, and **playable references** the UI can render. Phase 0 held
the choice open behind an explicit decision gate rather than assuming one, and
`PROVIDER_MODE` was declared as a feature flag with three legal values before any
provider code was written:

| Mode | Select when | Architecture |
| ---- | ----------- | ------------ |
| `musicapi` | Search, taste, playlist writes, error handling, cost and reliability all pass | All provider operations go through MusicAPI |
| `hybrid` | MusicAPI is strong for auth/data but a direct API is better for a critical operation | The adapter routes each operation to the chosen backend |
| `direct` | P0 capability, cost, reliability or terms fail | Direct YouTube-first API; optional direct Spotify adapter |

The candidate under test was **MusicAPI.com**, whose stated appeal was a single
unified authentication layer across several streaming platforms. The specific
question that mattered for Melody was not convenience but reach: **Spotify's
Development Mode caps an unapproved app at 5 authorized users**, and a project
that can only ever serve 5 people cannot be the primary recommendation path.

Evidence: `poc/test_musicapi.py` (`PROV-POC-001…011`, run 2026-07-21).

## Decision

**`PROVIDER_MODE=direct`.**

1. **MusicAPI is REJECTED.** It is a proxy in front of the same platform APIs and
   does not, and cannot, remove Spotify's platform-level 5-user Development Mode
   restriction. A unified auth layer does not confer platform authorization.
2. **Direct YouTube is APPROVED as the primary adapter.** YouTube Data API v3
   `search.list` needs only a project API key for reads, and `playlists.insert` /
   `playlistItems.insert` need only the user's own OAuth grant — neither has a
   per-app user cap, so any visitor can receive a recommendation and any
   signed-in user can export one.
3. **Direct Spotify is APPROVED but LIMITED**, and the limit is on *user-authorized*
   operations only — the 5-user cap binds taste import and playlist writes, not
   catalogue reads.

The mode is not a runtime negotiation: `PROVIDER_MODE` is read as configuration,
and provider-specific behaviour lives entirely inside `provider-gateway`.

## Rationale

1. **The deciding factor is reach, and it is binary.** MusicAPI's proxying leaves
   Spotify's cap exactly where it was. Every other axis (cost, latency, ISRC
   coverage, error semantics) was moot once the P0 capability failed — this is the
   `direct` row's own selection criterion: *"P0 capability, cost, reliability, or
   terms fail."*
2. **`hybrid` was rejected as well, not merely not-chosen.** Routing individual
   operations through MusicAPI would have kept a paid third-party dependency and a
   second failure mode on the request path, in exchange for an auth convenience
   the project does not need — Melody authenticates its users with Google OIDC
   (§5.2), not with a music platform.
3. **A dependency fewer before a deadline.** Direct APIs put the failure surface
   where it can be diagnosed: a YouTube quota error is a YouTube quota error, not
   a proxy's interpretation of one.
4. **The adapter contract absorbs the choice either way.** §3.5 requires every
   provider to normalize to the same operations and the same `NormalizedTrack`
   shape, so this decision was reversible in principle. It was proven reversible
   in practice: swapping the Phase 4 fixture for the real YouTube adapter required
   **zero** changes in `recommendation-service`, and adding Spotify later required
   none either.

## Consequences

**Accepted:**

- Melody owns YouTube-specific work that MusicAPI would nominally have hidden:
  quota accounting (`search.list` costs 100 units against a 10,000/day project
  budget), title/artist parsing from free-text video titles, and inferring
  whether a result is even music. This is real, ongoing cost — see §5.3.
- Two OAuth relationships instead of one (Google for identity + YouTube writes,
  Spotify optionally and separately).
- **YouTube result *selection* quality is Melody's problem to solve on YouTube's
  own terms.** There is no escape hatch to a curated catalogue, because of the
  Spotify decision below.

**Rejected deliberately:**

- Treating provider IDs as raw audio access. `PLAY-003` forbids downloading,
  isolating, proxying or modifying YouTube audio; playback is the official embed.

## Amendment (2026-07-26): Spotify's role, revised twice

Neither amendment changes `PROVIDER_MODE`; both change what Spotify is *for*.

1. **Spotify was promoted from an optional P1 slice to a first-class
   recommendation mode** (§5.6), reachable from a two-state UI toggle. This became
   possible on a finding the Phase 0 POC did not test: **Spotify catalogue search
   authenticates with the Client Credentials flow**, which is an application
   credential and therefore *not* subject to the 5-user Development Mode cap.
   The cap binds user-authorized resources — taste import, playlist writes — and
   those alone. So Spotify search works for every visitor, including guests.
2. **YouTube remains the default provider**, decided the same day after Spotify
   demonstrably returned better music for the same prompts. The reason is
   unchanged from this ADR's core: the parts of Spotify that would matter for a
   full product — importing a user's taste, writing a playlist back — remain
   capped at 5 users. **Spotify's real role is taste import for personalization**,
   not serving the request path by default.

Playlist export is therefore implemented for YouTube only; `/providers/playlists`
returns `PROVIDER_NOT_IMPLEMENTED` for Spotify, and the UI hides the export
control on a Spotify track rather than offering a write that would fail at the
provider after the user confirmed it.

## Why this file is late

The decision was made and recorded in `MELODY_AI_ORDERED_EXECUTION_PLAN.md` §0.4
on 2026-07-21, and §0.4 instructed that it also be committed here. That step was
missed. The gap was **surfaced by `ACA-002`'s traceability matrix** on 2026-07-24,
which logged it honestly as *"Decided, unrecorded"* rather than as done, and it
stayed open until this file was written on 2026-07-28.

Nothing in the decision changed in the interval — the implementation has followed
it since Phase 5 — but a decision that exists only inside a 400 KB plan document
is not a decision record, which is the point of keeping ADRs as separate files.
