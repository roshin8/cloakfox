# Cloakfox — agent instructions

**The instructions live in [CLAUDE.md](CLAUDE.md). Read that file.**

This file exists because `AGENTS.md` is the cross-tool convention, but it is
deliberately a pointer rather than a copy.

It started as a byte-identical duplicate of `CLAUDE.md`. Two copies of the same
instructions is a drift hazard: one gets updated, the other quietly goes stale,
and an agent reading the stale one works from architecture that no longer
exists. This repo already has a live example — `additions/cloakcfg/MaskConfig.hpp`
drifted from the patched copy in `firefox-src` and now documents a
`userContextId` parameter that it accepts and ignores, which is how a
container-resolution bug stayed invisible.

The risk is concrete here: `CLAUDE.md` documents a **cpp-first** architecture
with no MAIN-world inject scripts, and describes the earlier inject-based design
only as history. A stale duplicate would send an agent to build against the
removed design.

If you are adding tool-specific guidance, put the shared content in `CLAUDE.md`
and keep only the tool-specific delta here.
