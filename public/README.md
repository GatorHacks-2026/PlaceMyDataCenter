# Static assets (Vite `public/`)

Files in this folder are served from the site root. For example,
`public/agent-battle.png` is available in the app at `/agent-battle.png`.

## Agentic Battle loading image

The Agentic Battle feature shows a loading illustration of the two debating
agents (the green "advocate" and the red "challenger").

- **Drop the provided artwork here as `agent-battle.png`** (1024×576 or similar
  16:9 works best).
- If that file is **absent**, the UI automatically falls back to a built-in
  animated SVG of the two agents, so the feature still works with no missing
  images. No code change is needed either way.

Recommended: a transparent or dark-background PNG/WebP so it blends with the
navy theme.
