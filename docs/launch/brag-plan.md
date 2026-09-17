# Brag plan: agent-assurance

Invocation: `/brag --tone polished --format landscape --duration 22` — voice off, music on, sfx on.

## Rubric

1. **What is the app?** A deterministic CLI + GitHub Action: you declare what an AI agent may do (`agent-assurance.yaml`), it observes what the repo's configuration actually grants (MCP servers, Claude Code permissions) and fails the change when the promise is broken, pointing at file:line.
2. **Most impressive claim:** "Declare what your agent may do. Verify it on every edit, every PR, every release." Supporting line: "no LLM in the verdict".
3. **Visual hook:** the PR comment — `❌ PROMISE BROKEN BY THIS CHANGE` with `github.write grants write, not declared (.mcp.json:17)`.
4. **Show from the actual UI:** the promise YAML (`autonomy: 2  # a human approves actions`), the `.mcp.json` diff adding a GitHub server, and the PR comment (real copy from docs/pr-comment.png).
5. **Shortest satisfying video:** 22s. Hook 3.5s → the change 5s → verdict 7s → three enforcement points 3.5s → outro 3s.
6. **Tone:** `polished` (user-specified). Direction: quiet premium security-tool film; restraint; terminal/monospace UI on near-black; one accent red for the broken promise, one green for the promise.
7. **Audio:** low warm bed (`happy-beats-business-moves-vol-1`, 120 BPM), volume ~0.35, fade in 0–1s, fade out 20–22s. SFX: one soft landing when the GitHub block drops in, one short error cue on the ❌ verdict, one soft bong on the final logo. Nothing else.
8. **Share caption:** "Introducing agent-assurance: declare what your AI agent may do, verify it on every change — no LLM in the verdict, evidence signed per commit."
9. **User flow:** write the promise → a PR adds a tool → the PR comment blocks it and says why → (evidence) attestation. Centerpiece = scene 3, the PR verdict.

## Storyboard (22.0s total, 1920×1080)

| # | t | Scene | On screen | Motion | SFX |
|---|---|---|---|---|---|
| 1 | 0.0–3.6 | The promise | `agent-assurance.yaml` card, monospace: `tools: crm.read` · `autonomy: 2  # a human approves actions`. Kicker above: "Your agent has a job description." | Lines fade/rise in one by one (0.2s apart); kicker settles at 0.6s. Hold to 3.6. | — |
| 2 | 3.6–8.8 | The change | `.mcp.json` editor card. Existing lines dim; a new block slides in at line 17: `"github": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" } }`. Caption: "Then someone adds a tool." | Slow crossfade 0.7s from scene 1. Block rises in over 0.5s and settles; line number 17 highlights. | impactSoft_medium on block landing (~4.9s) |
| 3 | 8.8–15.8 | The verdict | PR comment card (real copy): header "Agent Assurance — what this change does" · `❌ PROMISE BROKEN BY THIS CHANGE` · `Blast radius: LOW → HIGH` · `Promise (AA-002): PASS → FAIL` · "Newly broken: `github.write` grants **write**, not declared (.mcp.json:17)". Caption below: "File and line. No LLM in the verdict." | Crossfade 0.7s. Card rises; header at 9.3; ❌ line lands 9.9 (beat 10.02); Blast/Promise lines 10.5/11.0; broken line 11.6; caption 12.6. Hold to 15.8. | error_005 on ❌ line (9.9) |
| 4 | 15.8–19.2 | Three enforcement points | Three lines, one per beat (16.02 / 17.02 / 18.02): "While the agent edits." · "In the pull request." · "On every release — signed." Small footer: Claude Code · Cursor · Gemini CLI · VS Code | Crossfade 0.6s; each line rises 24px and fades in over 0.4s, locked to strong cues. | — |
| 5 | 19.2–22.0 | Outro | `agent-assurance` wordmark · "Declare what your agent may do. Verify it on every change." · `pipx install agent-assurance` | Crossfade 0.7s; wordmark scales 0.96→1 over 0.6s; tagline fades in at 19.9; install line at 20.5. Hold. | bong_001 at 19.4 |

Reading time check: longest sentence (10 words) holds ≥3s; PR card lines hold ≥3.5s after the last settles.

## Music cue guidance

- Track: `happy-beats-business-moves-vol-1-by-ende-dot-app.mp3`, 120.19 BPM (bundled preset `assets/music/cues/…vol-1…music-cues.json`).
- Strong cue locks (3): ❌ verdict at 10.02 (beat), and the enforcement lines at 16.02 / 17.02 / 18.02 (strong cues).
- Beat-grid windows for the PR card sequential reveal: 10.02, 10.52, 11.02, 11.52.
- Restraint: polished tone — no pulsing, no audio-reactive strobing; at most a subtle background warmth tied to RMS if cheap, otherwise none.

## Handoff posture

/brag owns copy, angle, order, tone, audio selection. Hyperframes owns exact easings, transition mechanics, SFX filenames/timestamps, and render.
