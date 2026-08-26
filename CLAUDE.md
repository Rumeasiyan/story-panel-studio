@AGENTS.md

## Claude-specific notes

- **Subagents do not inherit this context.** When delegating, restate the constraints
  that apply to the delegated work — especially the localhost binding on ComfyUI and the
  rule that user input never becomes graph structure. A subagent given "add a pipeline"
  with no context will happily accept a caller-supplied graph. The same applies to
  narration: restate the locked engine and anchor from `config/voice-locks.yaml`, or a
  subagent will pick whichever engine sounds best on paper and silently re-voice a
  channel.
- **Verify by running.** This repository has no test suite. Three real bugs here were
  invisible to review and only surfaced on execution: uploads silently dropped by an
  `isinstance` check against the wrong `UploadFile` class, whisper failing on first
  transcribe rather than at load, and deleted prompts surviving in the SQLite WAL. Read
  the code, then run the path.
- **Do not trust `grep` in this shell for safety checks.** It is a wrapper that respects
  `.gitignore`, so it silently skips `output/`, `models/` and `service/data/` — exactly
  where generated content lives. Use `/usr/bin/grep` when verifying that something is
  really gone.
- **Long-running work belongs in the background.** Model downloads and video renders
  outlast a foreground tool call. Start them with `setsid nohup ... &` so they survive
  the session, and note that `pgrep -f "some command"` matches its own shell — a wait
  loop written that way deadlocks on itself.
