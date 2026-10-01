# LLM recordings (VCR-style)

Recorded responses replayed by `MockLLMClient` so Phase 3 tests never call a live model in CI
(spec §30.2, ADR-0009). Each file is `<key>.json`, where `<key>` is the first 16 hex chars of
`sha256(json.dumps({"model", "messages"}, sort_keys=True))` (see `app/providers/mocks/llm.py`).

```json
{
  "kind": "text | json",
  "model": "claude-haiku-4-5",
  "prompt_summary": "human note about what this prompt was",
  "response": "..."        // string when kind=text, object when kind=json
}
```

Only one illustrative recording exists now; real recordings are captured in Phase 3 once an
LLM key is available. To (re)generate a key for a prompt, call `MockLLMClient`'s `_key(...)`.
