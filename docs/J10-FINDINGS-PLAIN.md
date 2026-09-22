# J10 in plain language: bring your own AI provider

## Your keys, your providers
Tierllama speaks the OpenAI protocol - which means almost every AI company
speaks it too. Drop your API key in an environment variable, add a few lines
of config, and your provider's models appear in the dashboard dropdowns with
real cost tracking per call. Have OpenAI keys? Your tree can route to Luna for
easy stuff and reserve the expensive models for the jobs that need them.

## New models arrive as data, not downloads
The "brain" of the recommendations - which models are good at what - ships as
a small, signed data file. On startup Tierllama checks: is there a newer one?
It verifies the file's fingerprint (so nobody can feed you tampered data),
stages it... and stops there. Nothing changes until YOU click "Re-scan models"
and see exactly which tiers will change - a preview, like a diff. Your custom
edits are always preserved, and one command rolls back if you don't like it.

Silent data, explicit decisions. That's the contract.
