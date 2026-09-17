# Hyperframes Composition Brief: agent-assurance

## Objective
Create a short launch-style brag video for agent-assurance.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 22 seconds

## Source Material
- Project root: `/Users/altostratus_1/Documents/Vane/kunko/agent-assurance`
- Primary files read: README.md, docs/video-script.md, docs/pr-comment.png, examples/demo/analytics-helper/agent-assurance.yaml, examples/demo/analytics-helper/.mcp.json
- Product name: agent-assurance
- Tagline / strongest claim: "Declare what your agent may do. Verify it on every edit, every PR, every release." · "No LLM in the verdict."
- Real copy to show verbatim: `autonomy: 2  # a human approves actions` · `❌ PROMISE BROKEN BY THIS CHANGE` · `Blast radius: LOW → HIGH` · `Promise (AA-002): PASS → FAIL` · `github.write grants write, not declared (.mcp.json:17)`

## Creative direction
- Tone: polished. Quiet premium security-tool film. Restraint as the choice.
- Palette (from the README's terminal look): background #0b0f14, surface #131a22, text #e6edf3, muted #8b98a5, accent red #f85149 (broken), accent green #3fb950 (promise), accent blue #58a6ff (links/keys).
- Typography: system UI sans for headings (light-to-medium weight, generous letter-spacing), system monospace for code/UI cards. No external fonts (lint requires local @font-face for named families).
- Transitions: slow crossfade 0.6–0.8s between scenes.

## Storyboard
See `brag-plan.md` (5 scenes, 22.0s). Scene 3 (PR verdict) is the centerpiece and must be the poster frame.

## Audio
- Audio arc: warm bed enters under the promise, holds under the change, the verdict lands with one dry error cue, the bed thins under the enforcement lines and fades out under the logo with a single soft bong.
- Music: `assets/music/happy-beats-business-moves-vol-1-by-ende-dot-app.mp3`
- Music treatment: volume 0.35, fade in 0–1.0s, fade out 20.0–22.0s via `data-automation` volume lane.
- Music cue guidance: bundled preset `assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json`; locks at 10.02 (verdict), 16.02/17.02/18.02 (three lines).
- Audio-reactive treatment: none (polished; keep it still).
- Audio-coupled moments: GitHub block landing (~4.9s) — soft impact; ❌ verdict (9.9s) — short error cue; final wordmark (19.4s) — soft bong.
- SFX selection guidance: low high-frequency-risk files only; three SFX total.
- Exact SFX choice: `assets/sfx/impact/impactSoft_medium_000.ogg`, `assets/sfx/interface/error_005.ogg`, `assets/sfx/interface/bong_001.ogg`.
- Audio files: copied into `brag-output/composition/assets/`.

## Hyperframes Instructions
Follow `hyperframes-core` (one paused GSAP timeline registered as `window.__timelines["main"]`, `data-start`/`data-duration` on every clip, `class="clip"`, no CSS transform + GSAP conflict, every `<audio>` with an id, no `<br>` in body text, deterministic only) and `hyperframes-cli` (`npx hyperframes check` as the single gate, then `render --quality delivery`).

Requirements:
- Show real UI/copy from the project (scenes 1–3 are verbatim).
- Keep all text readable; WCAG contrast must pass `check`.
- 22 seconds exactly (`data-duration="22"` on the root).
- Music + three SFX as above.
