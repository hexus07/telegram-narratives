Appendix A. Relevance agent

Model: Claude Opus 5.5 (claude-opus-5-5), accessed via the Claude Code CLI agent (Anthropic API), run on 26 October 2026.
Settings: Medium effort, max tokens default, tools: file read/write, shell.
Task: read posts from channels.json (using custom scraper script with predefined keywords for each domain from selected 14 channels), judge whether each contains a narrative, write results to domain_annotation.csv.
Prompt: 
Select posts on two domains: the Russia–Ukraine war and migration. Keep only posts
where the text assigns agency, causality or moral evaluation to entities. Truthfulness is
not a criterion. Skip purely factual posts.

Topics:
- War: military events, political decisions, aid, mobilisation, peace talks or actors of the Russia–Ukraine war as the main subject, not background.
- Migration: migrants, refugees, asylum, borders, deportation or migration policy as the main subject.

Narrative Rule: present when the text assigns agency, causality or moral evaluation to entities. Truthfulness is not a criterion.

Output: Only selected posts, one row per post with fields: message_id, channel, date, domain, language, url, text, side(defined manually for each channel) saved to domain_annotation.csv.

