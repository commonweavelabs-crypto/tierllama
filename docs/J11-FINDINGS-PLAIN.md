# J11 in plain language: a dashboard with real pages

## Tabs, not one endless scroll
The dashboard now has four tabs: **Overview** (test a route, savings, fleet),
**Routing** (optimize, model suggestions, the advanced decision tree),
**Providers**, and **Activity** (the decision log). Everything you knew is
still there - just organized.

## The Providers tab
Every provider gets a card with its logo, an on/off toggle, and a key-status
dot: green when your API key is found, amber when it's missing. Paste a key,
hit Save, and that provider's models appear in your routing dropdowns - no
restart. Keys are stored in a local file that git ignores; they never touch
the repo or any log.

And remember the taxonomy: Ollama is ONE provider - your local models and
cloud-tagged models all live under its card.
