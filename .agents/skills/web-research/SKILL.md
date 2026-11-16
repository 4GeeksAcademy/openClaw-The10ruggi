---
name: web-research
description: Research questions using supplied URLs or accessible web pages; produce a sourced synthesis with explicit evidence limits.
---

# Web Research

1. Parse the request into a concrete question, requested scope, time period, and desired language; ask one focused question only if a missing detail prevents a useful, bounded answer. Default to Spanish and a concise response, because the user prefers Spanish and direct answers.
2. Check the available research tools before collecting evidence. Use `web_fetch` to read known URLs and `browser` only when page navigation or JavaScript interaction is needed. General `web_search` is not configured in this environment, so do not claim to have searched the web or discovered sources through it; if no URLs or usable sources are available, explain the limitation and ask for starting links or a working search capability.
3. Read each relevant source with `web_fetch` or `browser` and record its title, URL, publication/update date when visible, and the exact claims it supports; do not cite pages that were not successfully inspected.
4. Compare claims across independent sources when the question warrants it; distinguish source-backed facts from inference, note conflicts and freshness limits, and avoid presenting unsupported or uncertain claims as established facts.
5. Return the result in Markdown in the current chat unless the user requests another destination. Lead with a concise answer, organize material findings, attach source links to the claims they support, and finish with material caveats or unanswered questions. Do not publish or send the research elsewhere without explicit authorization.
6. Verify before responding that every material factual claim is traceable to a source actually read, cited links correspond to those sources, dates and uncertainty are clear, and the answer does not imply unavailable search capability. If the supplied URLs cannot support the requested scope, report that limitation rather than filling gaps with invented research.
