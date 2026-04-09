# MEX Process Bot

Automated process Q&A support for the Member Experience team. The bot watches a Slack channel, looks up process documentation, and drafts sourced answers — with human review before anything goes live.

## Quick Start

```
git clone https://github.com/thensls/mex-process-bot.git
cd mex-process-bot
```

See [docs/how-it-works.md](docs/how-it-works.md) for the full guide.

## Current Status

The bot is in testing mode, posting drafts to the test channel. MEX reviewer TBD.

## Architecture

Same pattern as [cs-tech-triage](https://github.com/thensls/cs-tech-triage):
- Python 3.12, stdlib only (no pip dependencies)
- Railway cron every 10 minutes
- Claude API for classification + response generation + scoring
- Airtable for tracking response quality
- Shadow mode: drafts go to test channel, never posts to live channel

## Questions?

Reach out to the MEX team lead or Kevin.
