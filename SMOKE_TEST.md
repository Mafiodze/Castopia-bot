Castopia Bot Smoke Test

This checklist validates the current Castopia Bot after code, dependency, or deployment changes.

It covers the Discord bot, Telegram bot, shared WikiClient, configuration, error handling, caching, pagination, and deployment behavior.

1. Test prerequisites

Before running the smoke test, verify that:

	●	the project is using the current supported Python version;
	●	dependencies from the root requirements.txt are installed;
	●	.env is configured locally or the required variables are present in the deployment environment;
	●	DISCORD_BOT_TOKEN is available for Discord tests;
	●	TELEGRAM_BOT_TOKEN is available for Telegram tests;
	●	WIKI_BASE_URL points to the intended public wiki;
	●	WIKI_USER_AGENT is non-empty;
	●	WIKI_MAX_CONCURRENCY is between 1 and 10;
	●	DISCORD_GUILD_ID is set only when guild-specific command synchronization is desired;
	●	no real secrets are printed in terminal output or logs.

For local testing, keep the test account and test guild separate from production where practical.

2. Basic project checks

Run:

```text
python -m compileall cogs dsc tg tests
python -m unittest discover -s tests -v
```

Acceptance:

		Python compilation succeeds.
		All discovered tests pass.
		No import error occurs.
		No traceback is produced during normal startup.
		No generated .pyc, __pycache__, or .pkl files are added to Git.

3. Discord bot startup

Start:

```text
python dsc/bot.py
```

Check:

		Bot starts without configuration errors.
		Discord Gateway connection succeeds.
		cogs.dsc loads successfully.
		WikiClient starts successfully.
		Application commands synchronize successfully.
		No authentication token is printed.
		No unexpected exception occurs during startup.

If DISCORD_GUILD_ID is set:

		Commands synchronize to the specified development guild.

If DISCORD_GUILD_ID is not set:

		Commands synchronize globally.

Do not assume that global command propagation is immediate.

4. Discord prefix commands

The prefix is ..

.help

		Command responds.
		Help text is readable.
		The listed commands correspond to the current bot commands.
		No malformed Discord Markdown or embed formatting appears.

.search <query>

Test:

```text
.search <known article>
.search <partial article name>
.search <nonexistent article>
```

Check:

		Exact or partial title search returns the expected article when available.
		Unknown articles return a normal not-found response.
		Article title is displayed correctly.
		Article URL is clickable.
		Excerpt is readable.
		Very long input is rejected.
		Rate limit is enforced at 3 requests per 20 seconds per user.

.randompage

Check:

		A public article can be returned.
		System-tagged articles are excluded.
		Missing/stale pages do not crash the command.
		Article URL and excerpt are displayed.
		Rate limit is enforced at 2 requests per 20 seconds per user.

.tags <tag> [tag...]

Test:

```text
.tags <known tag>
.tags <tag1> <tag2>
.tags <unknown tag>
```

Check:

		Known tags return matching articles.
		Multiple tags are handled correctly.
		Unknown tags return an empty result without crashing.
		System-tagged articles remain excluded where applicable.
		No more than 5 tags are accepted.
		Excessively long tags are rejected.
		Results are rendered as a readable embed.
		No more than 20 result fields are displayed by the Discord adapter.
		Rate limit is enforced at 2 requests per 30 seconds per user.

.fullsearch <query>

Check:

		Full-text search returns real articles when the query exists.
		Unknown queries return an empty result message.
		Results are relevance-sorted.
		Pagination appears when more than 5 results exist.
		Five results are shown per page.
		Previous/next buttons work.
		First page disables previous.
		Last page disables next.
		Only the original requester can use the buttons.
		Search state expires after its configured view timeout.
		Rate limit is enforced at 1 request per 30 seconds per user.

5. Discord slash commands

Verify:

```text
/help
/search
/randompage
/tags
/fullsearch
```

For every slash command:

		Discord interaction is acknowledged before the three-second interaction deadline.
		Long-running commands enter the deferred/thinking state.
		The final result is delivered successfully after defer/followup handling.
		No This interaction failed message appears.
		Error responses remain user-readable.
		Prefix and slash commands produce equivalent functional results.

For /search:

		Autocomplete starts after at least 2 typed characters.
		Suggestions are limited to Discord’s supported maximum.
		Suggestions are readable and selectable.
		Autocomplete timeout does not produce a visible bot error.

6. Discord pagination and UI

For .fullsearch or /fullsearch with enough results:

		SearchResultsView displays five articles per page.
		Page indicator shows current page and total pages.
		Article titles are readable.
		Excerpts are readable.
		Article links work.
		Buttons are disabled appropriately at boundaries.
		A different Discord user cannot operate the original user’s pagination controls.
		Expired views no longer accept useful navigation.
		Timeout cleanup does not generate repeated exceptions.

7. Telegram bot startup

Start:

```text
python tg/bot.py
```

Check:

		Bot starts without configuration errors.
		Telegram polling starts successfully.
		cogs.tg imports successfully.
		The same shared WikiClient architecture is used.
		No token is printed.
		No unexpected startup traceback occurs.

8. Telegram commands

Test:

```text
/start
/help
/search <query>
/randompage
/tags <tag> [tag...]
/fullsearch <query>
```

Check:

		/start and /help display current commands.
		/search returns title-search results.
		/randompage returns a public article when available.
		/tags returns matching articles.
		/fullsearch returns full-text results.
		Unknown searches produce a normal empty-result response.
		Long queries are rejected cleanly.
		More than 5 tags are rejected cleanly.
		Long tags are rejected cleanly.
		Telegram HTML remains valid.
		Article links work.

9. Telegram full-search pagination

Run a query returning more than five results.

Check:

		Pagination buttons appear.
		Next page works.
		Previous page works.
		Page number is bounded to the valid range.
		Only the user who created the search can operate its pagination controls.
		Expired pagination state returns a clear message.
		Malformed callback data does not crash the handler.
		Missing callback message is handled safely.

10. Shared WikiClient behavior

The Discord and Telegram adapters must use the same WikiClient implementation.

Verify:

		A single aiohttp.ClientSession is reused by a client instance.
		Requests use the configured User-Agent.
		Requests stay within the configured wiki origin.
		HTTPS configuration is enforced.
		Request timeout is active.
		Concurrency remains bounded by WIKI_MAX_CONCURRENCY.
		401 and 403 are not retried.
		404 becomes a not-found condition.
		429 and appropriate 5xx responses are retried within the configured retry policy.
		Failed upstream requests eventually become a safe user-facing error.
		HTML structure errors produce UpstreamContentError.
		No access-control bypass or CAPTCHA/WAF bypass is attempted.

11. Caching

Validate behavior rather than assuming a specific TTL.

Check:

		First request performs the required upstream fetch.
		Immediate repeated requests can use the in-memory cache.
		Expired entries are eventually removed.
		Cache does not depend on repository cache.pkl.
		Cache state is not committed to Git.
		Cache growth remains bounded.
		Search cache behaves consistently for repeated queries.
		Full-text searches remain serialized according to the current WikiClient search lock design.

Do not require a specific number of minutes in this checklist unless the current code explicitly defines and intentionally preserves that value.

12. Concurrency

Run several requests at the same time.

Check:

		Bot remains responsive.
		No uncontrolled task creation occurs.
		No excessive simultaneous upstream requests occur.
		The configured concurrency limit is respected.
		A failed request does not cancel unrelated requests unexpectedly.
		Batch operations remain bounded.
		Multiple concurrent requests for the same URL do not trigger unnecessary duplicate fetches.

13. Error handling

Access denied

Simulate or use a controlled response producing 401 or 403.

Verify:

		User receives an access-denied message.
		No retry loop occurs.
		No bypass attempt occurs.

Rate limiting

Simulate 429.

Verify:

		Retry behavior follows the current WikiClient policy.
		Retry-After is respected when supplied.
		Retry count remains bounded.

Server failure

Simulate 500, 502, or 503.

Verify:

		Retries are bounded.
		Final failure produces a safe message.
		Logs contain useful diagnostic information without secrets.

Missing page

Simulate 404.

Verify:

		It becomes an UpstreamNotFoundError.
		Random/search/tag functionality can handle the missing article without crashing.

HTML structure change

Provide malformed or changed HTML.

Verify:

		UpstreamContentError is raised where structural validation is required.
		The bot remains operational for unrelated requests.
		The user sees a generic structural-change message rather than a traceback.

14. Security checks

Search the repository for:

```text
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
password
secret
api_key
cookie
```

Check:

		No real credentials are committed.
		No token is printed in debug output.
		.env is ignored by Git.
		Runtime cache files are ignored.
		.pyc and __pycache__ are ignored.
		No user credentials are stored in JSON or pickle.
		URLs requested by WikiClient remain same-origin.
		Untrusted HTML is escaped before Telegram output.
		Untrusted text cannot freely alter Discord Markdown layout.

Never paste real tokens into this document or its output.

15. Logging

Confirm that logs contain useful information such as:

```text
wiki_request status=... duration_ms=... attempt=...
wiki_fetch cache_hit=...
wiki_search ...
discord_command ...
telegram_command ...
```

Check:

		No credentials appear in logs.
		Errors identify the relevant subsystem.
		Command timing is present where intended.
		Logs do not become excessively verbose at normal INFO level.
		Debug logging can be enabled without exposing secrets.

16. Configuration

Test valid configuration:

```text
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=<non-empty value>
WIKI_MAX_CONCURRENCY=4
```

Test invalid configuration:

```text
WIKI_BASE_URL=http://example.com
WIKI_BASE_URL=https://example.com/path
WIKI_BASE_URL=https://user:password@example.com
WIKI_MAX_CONCURRENCY=0
WIKI_MAX_CONCURRENCY=11
WIKI_MAX_CONCURRENCY=abc
WIKI_USER_AGENT=
```

Check:

		Valid configuration loads successfully.
		Invalid configuration raises ConfigurationError.
		Error messages explain which configuration value is invalid.
		No secret value is included in configuration errors.

17. Deployment checks

Docker

Build:

```text
docker build -t castopia-bot .
```

Check:

		Image builds successfully.
		No runtime source files are missing.
		.env and other secrets are not copied into the image.
		Cache/build artifacts are not included unnecessarily.
		The intended startup command launches the correct bot process.

Docker Compose

Check each configured profile independently.

		Discord profile starts the Discord bot.
		Telegram profile starts the Telegram bot.
		Combined profile starts both when intended.
		Environment variables reach the container.
		No conflicting process configuration exists.

Railway

Check:

		railway.json matches the actual Docker/startup configuration.
		Required environment variables are configured.
		The application starts without manual local files.
		Restart behavior is appropriate for failed processes.
		No documentation-only deployment claims are treated as verification.

Do not mark Railway as operational without an actual deployment or runtime verification.

18. Final acceptance criteria

The smoke test passes only when all applicable checks below are true:

		Discord bot starts.
		Telegram bot starts.
		Shared WikiClient imports and initializes.
		.search / /search work.
		.randompage / /randompage work.
		.tags / /tags work.
		.fullsearch / /fullsearch work.
		Discord autocomplete works.
		Discord pagination works.
		Telegram pagination works.
		Rate limits behave as configured.
		Upstream errors are handled without crashes.
		Configuration validation rejects unsafe or malformed values.
		No secrets are exposed in logs or committed files.
		Runtime cache remains outside Git.
		Tests pass.
		Docker configuration is internally consistent.
		Railway configuration is internally consistent if Railway is being used.

19. Reporting

Record results using:

```text
Smoke test date:
Commit:
Python version:
Dependency installation:
Discord:
Telegram:
WikiClient:
Tests:
Docker:
Railway:
Security:
Known limitations:
```

Use only verified results.

Do not report a component as PASS if it was only inspected statically.

For external services that were not available during testing, mark the result as NOT RUN and explain why.