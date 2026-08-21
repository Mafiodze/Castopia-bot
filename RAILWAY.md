Railway Deployment Guide
This document describes the current deployment process for Castopia Bot on Railway.
Current deployment architecture:
Railway
   ↓
railway.json
   ↓
Dockerfile
   ↓
/app/start.sh
   ├── dsc/bot.py
   └── tg/bot.py
        ↓
   shared WikiClient
Railway uses Docker deployment. Procfile is not the current Railway startup mechanism.
1. Requirements
The deployment requires:
	•	GitHub repository containing the project;
	•	a Railway account;
	•	a Discord Bot Token;
	•	a Telegram Bot Token;
	•	container access to the Wiki over HTTPS.
The current Docker image uses Python 3.12.
2. Creating the Project
In Railway:
	1.	Create a new Project.
	2.	Choose deployment from a GitHub repository.
	3.	Connect Mafiodze/Castopia-bot.
	4.	Make sure Railway detects railway.json.
The current project configuration tells Railway to use:
builder: DOCKERFILE
dockerfilePath: /Dockerfile
startCommand: ./start.sh
Do not configure a separate Procfile startup command instead of this configuration.
3. Environment Variables
Add the variables in Railway Dashboard → Variables.
Required for Discord:
DISCORD_BOT_TOKEN=...
Required for Telegram:
TELEGRAM_BOT_TOKEN=...
Wiki configuration:
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=CastopiaBot/2.0
WIKI_MAX_CONCURRENCY=4
Optional Discord development configuration:
DISCORD_GUILD_ID=...
Optional logging level:
LOG_LEVEL=INFO
Do not store real tokens in .env if that file is included in or passed through the deployment context.
Railway environment variables should be configured through Railway Variables.
4. What Happens During the Build
The Dockerfile:
	1.	Uses python:3.12-slim.
	2.	Installs the system dependencies required by the project’s Python packages.
	3.	Copies the root requirements.txt.
	4.	Installs the Python dependencies.
	5.	Copies the project into /app.
	6.	Makes /app/start.sh executable.
	7.	Starts /app/start.sh.
Sources of truth:
Dockerfile
requirements.txt
start.sh
Do not rely on old deployment summaries when troubleshooting the deployment.
5. What Happens at Startup
start.sh starts two independent Python processes:
python -u /app/dsc/bot.py
python -u /app/tg/bot.py
Discord:
dsc/bot.py
    ↓
cogs.dsc
    ↓
WikiClient
Telegram:
tg/bot.py
    ↓
cogs.tg
    ↓
WikiClient
After startup, start.sh monitors both processes and attempts to restart a process if it exits.
If one bot keeps restarting, look for the original error in its logs. Do not increase restart limits without understanding the cause.
6. First Deployment
After adding the environment variables, click Deploy.
After startup, open Railway Logs.
A normal startup should show:
	•	Discord process starting;
	•	Telegram process starting;
	•	initialization or connection of the corresponding clients;
	•	no configuration errors;
	•	no endless restart loop.
Do not consider the deployment successful based only on the Running status.
7. Discord Verification
After deployment:
.help
.search <known article>
.randompage
.tags <known tag>
.fullsearch <query>
Also test the slash commands:
/help
/search
/randompage
/tags
/fullsearch
Test /search autocomplete and pagination for full-text search.
If DISCORD_GUILD_ID is set, commands are synchronized to the specified development guild.
If it is not set, global application commands are used.
Do not consider missing global commands a runtime failure without accounting for Discord application command propagation delays.
8. Telegram Verification
After deployment:
/start
/help
/search <known article>
/randompage
/tags <known tag>
/fullsearch <query>
Check:
	•	valid HTML formatting;
	•	links;
	•	pagination;
	•	prevention of other users from using someone else’s results;
	•	behavior of expired pagination tokens.
9. Wiki Verification
Minimum configuration to check:
WIKI_BASE_URL
WIKI_USER_AGENT
WIKI_MAX_CONCURRENCY
Make sure that:
	•	the Wiki is accessible over HTTPS;
	•	the User-Agent is not empty;
	•	concurrency is within the allowed range;
	•	401/403 responses are not bypassed;
	•	429 and temporary 5xx responses are handled according to the retry policy;
	•	404 is handled correctly;
	•	changes to the HTML structure result in a diagnosable error.
Do not add mechanisms to bypass CAPTCHA, WAF, or access controls.
10. Rate Limiting and Concurrency
Discord has internal command rate limiting.
Current limits:
search      3 / 20 sec
tags        2 / 30 sec
randompage  2 / 20 sec
fullsearch  1 / 30 sec
Wiki concurrency is controlled by:
WIKI_MAX_CONCURRENCY
Allowed configuration range:
1..10
Recommended default:
4
Increasing concurrency does not guarantee better performance and may increase the number of 429 responses from the Wiki.
11. Cache
The project’s cache is runtime state.
Do not:
	•	upload cache.pkl as part of deployment;
	•	commit cache files to Git;
	•	carry local state between deployments;
	•	rely on an old repository cache.
Verify cache behavior through the application:
	•	the first request performs the necessary upstream work;
	•	repeated requests may use the in-memory cache;
	•	expired entries are removed;
	•	cache does not grow without bounds.
Exact TTL values should be determined by the current WikiClient implementation rather than by this document.
12. Logs
Use Railway Logs for diagnostics.
Expected log categories:
wiki_request
wiki_fetch
wiki_links
wiki_search
discord_command
telegram_command
discord_rate_*
The following must never appear in logs:
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
cookies
API keys
passwords
Do not enable DEBUG logging permanently in production.
13. Troubleshooting
Configuration error
Check Railway Variables:
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
WIKI_BASE_URL
WIKI_USER_AGENT
WIKI_MAX_CONCURRENCY
Discord process keeps restarting
Check the first traceback from:
dsc/bot.py
In particular:
	•	Discord token;
	•	intents;
	•	command synchronization;
	•	import errors;
	•	Wiki configuration.
Telegram process keeps restarting
Check:
tg/bot.py
In particular:
	•	Telegram token;
	•	polling conflicts;
	•	import errors;
	•	Wiki configuration.
Wiki returns 403
This means the source rejected the request.
Do not add a bypass.
Use the official API or another authorized access method.
Wiki returns 429
Check:
WIKI_MAX_CONCURRENCY
and the retry logs.
Do not automatically increase concurrency.
Slash commands are missing
If DISCORD_GUILD_ID is configured, verify its value.
If global synchronization is being used, account for the delay required by the Discord API to propagate application commands.
Both processes start, but one disappears
Check the traceback for the affected process. start.sh may restart the process, so look for the first actual error rather than only the restart message.
14. Manual Redeployment
After changing the code:
commit
→ push
→ Railway build
→ Docker image
→ start.sh
→ Discord + Telegram
After deployment, run the smoke test again.
Document:
SMOKE_TEST.md
15. Rollback
If a deployment has problems, use Railway’s deployment mechanism to return to the previous successful deployment.
Before rolling back, save:
	•	commit SHA;
	•	relevant logs;
	•	the error;
	•	environment variable changes, if any were recently made.
Do not change application code and deployment configuration simultaneously during troubleshooting unless necessary.
16. Docker Consistency
Railway and local Docker should use the same basic architecture:
Dockerfile
    ↓
start.sh
    ↓
dsc/bot.py
tg/bot.py
If local Docker and Railway behave differently, first compare:
	•	image;
	•	environment variables;
	•	working directory;
	•	file permissions;
	•	startup command;
	•	installed dependencies.
17. Security Checklist
Before production deployment:
	•	.env is not in Git.
	•	Discord token is not in Git.
	•	Telegram token is not in Git.
	•	No secrets are included in the Docker image.
	•	No secrets appear in logs.
	•	cache.pkl is not used as a deployment artifact.
	•	__pycache__ and .pyc files are not committed.
	•	Wiki URLs pass same-origin validation.
	•	Wiki access controls are not bypassed.
If a secret has been published in Git history, it must be revoked and replaced. Simply deleting the file from the current commit is not sufficient.
18. Deployment Acceptance
A Railway deployment should be considered verified only after the following have actually been checked:
Build: PASS
Startup: PASS
Discord: PASS / NOT RUN
Telegram: PASS / NOT RUN
Wiki: PASS / NOT RUN
Smoke test: PASS / NOT RUN
Running in the Railway Dashboard alone is not proof that both bots are working correctly.
19. Source of Truth
The primary files for the current Railway deployment are:
railway.json
Dockerfile
start.sh
requirements.txt
runtime.txt
For functional verification:
dsc/bot.py
tg/bot.py
cogs/dsc.py
cogs/tg.py
cogs/page_parsing.py
cogs/constants.py
For operational verification:
SMOKE_TEST.md
If this document and the actual configuration diverge, the actual configuration is considered authoritative, and the documentation should be updated.