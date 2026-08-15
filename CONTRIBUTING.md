# Contributing to makeaibilli

Contributions welcome. Here's how to make one that lands.

## Ground rules

1. **Never commit secrets.** `.env` is gitignored. If you add a new data
   source that needs a key, add it to `.env.template` with an empty value
   and document it in the README.
2. **Honesty over hype.** This project deliberately avoids claiming to
   predict prices. PRs that add "guaranteed signals" or overstate certainty
   will be declined. Ranges and probabilities, not promises.
3. **Respect data sources.** Every scraper must stay within its source's
   rate limits and terms of service. Add throttling for new sources.
4. **Hardware awareness.** This is designed to run on modest hardware.
   Avoid adding heavy dependencies or unbounded loops over large universes.

## Getting set up

```bash
git clone https://github.com/315v12/makeaibilli.git
cd makeaibilli
cp .env.template .env      # add your own Finnhub key
./build.sh
```

## Making a change

1. Fork, then branch: `git checkout -b feature/what-it-does`
2. Make your change
3. Verify everything still parses:
```bash
   cd src && python3 -c "
   import ast, glob
   for f in glob.glob('**/*.py', recursive=True): ast.parse(open(f).read())
   print('ok')"
```
4. Test locally with `./build.sh` and confirm the dashboard loads
5. Commit with a clear message, push, open a PR

## PR checklist

- [ ] No secrets, keys, or personal paths committed
- [ ] All Python parses
- [ ] Dashboard loads and tabs populate
- [ ] New dependencies added to `requirements.txt`
- [ ] README updated if behavior changed
- [ ] New data sources are rate-limited and documented

## Good first issues

- Additional scrapers (new RSS feeds, other social sources)
- Factor model improvements (new factors, better weighting)
- Backtesting harness — currently there is none
- Alternative data providers (Polygon, FMP) as yfinance fallbacks
- UI/UX improvements, especially mobile
- Tests (the project currently has none — this would be a big contribution)
