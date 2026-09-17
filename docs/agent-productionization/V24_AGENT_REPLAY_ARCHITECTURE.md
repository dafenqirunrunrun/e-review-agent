# V2.4 Agent Replay Architecture

- Replay is not retry. It uses frozen synthetic inputs and stub provider outputs.
- Structural replay verifies trace shape; deterministic replay verifies canonical outcome hash; provider stub replay avoids real external calls.
- ReplaySideEffectGuard blocks business writes, notifications, and external tool side effects.
