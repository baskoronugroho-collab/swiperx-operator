# `_handover/memory/` — assistant memory bundle

Copies of the assistant's persistent project memory from the origin device
(`C:\Users\NXP\.claude\projects\C--Users-NXP--claudeai-SwipeRx\memory\`), placed here so they
**travel with the `SwipeRx\` upload** — the real memory dir lives outside the project folder.

**To merge on a new device, see `CONTINUE_HERE.md` §4.** Short version: in a Claude session opened
in the SwipeRx folder, say *"read `_handover/memory/*.md` and save each into your project memory,
merging `MEMORY.md`."*

- `MEMORY.md` — the index (one line per memory; append these to the new device's index, don't overwrite).
- `swiperx-m1-deployed.md` — M0+M1 backend deployed & verified 09 Jul.
- `swiperx-deploy-api.md` — deploy without the plugin via the portal upload API.
- `swiperx-working-conventions.md` — spec churn expected; don't build the M2 courier module yet.

These are a convenience layer — the same facts live in `BUILD_HANDOFF.md` / `UNHAPPY_FLOWS.md`.
