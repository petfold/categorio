"""What crawlers may fetch.

robots.txt keeps every crawler out of the pages that never run out (category
combinations, the console, search, sign-in) and out of people's own pages,
and tells AI-training crawlers to stay away entirely. The AI crawlers are also
refused at the door (403), for any that ignore robots.txt: on 4 Oct 2026 GPTBot
alone made 311,595 of the site's 396,558 requests.
"""

# Tokens AI-training crawlers obey in robots.txt (some are not user agents:
# Google-Extended and Applebot-Extended only opt a site out of AI training).
AI_TOKENS = (
    "GPTBot", "ClaudeBot", "anthropic-ai", "CCBot", "meta-externalagent",
    "meta-externalfetcher", "Bytespider", "PerplexityBot", "cohere-ai",
    "Diffbot", "Omgilibot", "ImagesiftBot", "Google-Extended", "Applebot-Extended",
)

# Substrings of the user agents refused outright (lower case).
AI_AGENTS = tuple(t.lower() for t in AI_TOKENS if t not in ("Google-Extended", "Applebot-Extended"))

# Endless or personal: combinations (/q), console, search, completions, accounts,
# a person's store and the pages others share from theirs.
PRIVATE = ("/q", "/console", "/search", "/names", "/login", "/register", "/store", "/from/")

ROBOTS_TXT = "".join(
    [f"User-agent: {t}\nDisallow: /\n\n" for t in AI_TOKENS]
    + ["User-agent: *\n"]
    + [f"Disallow: {p}\n" for p in PRIVATE]
    + ["Disallow: /packs/*/download\n"]
)


def is_ai_crawler(user_agent: str | None) -> bool:
    ua = (user_agent or "").lower()
    return any(a in ua for a in AI_AGENTS)
