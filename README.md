# Castopia Bot

Discord and Telegram client for searching the public Castopia Wiki.

The project intentionally keeps a simple architecture:

```text
Discord
dsc/bot.py
    ↓
cogs/dsc.py
    ↓
cogs/page_parsing.py
    ↓
Castopia Wiki

Telegram
tg/bot.py
    ↓
cogs/tg.py
    ↓
cogs/page_parsing.py
    ↓
Castopia Wiki
Discord and Telegram use separate entry points and adapters, while sharing the same WikiClient and configuration layer.
Features
Discord
Hybrid commands are supported, so the same functionality is available through both prefix and slash commands:
.help
.search <title>
.randompage
.tags <tag> [tag...]
.fullsearch <text>
Slash commands:
/help
/search
/randompage
/tags
/fullsearch
Additional Discord functionality includes:
	•	autocomplete for /search;
	•	pagination for full-text search results;
	•	per-user and per-command rate limiting;
	•	interaction handling for slash and hybrid commands.
Telegram
/start
/help
/search <title>
/randompage
/tags <tag> [tag...]
/fullsearch <text>
Telegram supports:
	•	inline keyboards;
	•	callback queries;
	•	pagination for full-text search;
	•	HTML message formatting;
	•	long polling.
WikiClient
Shared Wiki logic is located in:
cogs/page_parsing.py
WikiClient is responsible for:
	•	asynchronous HTTP requests;
	•	bounded concurrency;
	•	timeout handling;
	•	retry handling;
	•	Wiki origin validation;
	•	HTML parsing;
	•	title search;
	•	tag search;
	•	full-text search;
	•	pagination;
	•	runtime caching;
	•	structured upstream error handling.
Discord and Telegram do not maintain separate Wiki implementations. Both adapters use the same WikiClient.
Runtime cache is application state. It is not part of the repository and does not depend on cache.pkl.
Requirements
The project uses Python 3.12 as its runtime target.
For local development you need:
	•	Python 3.12;
	•	pip;
	•	Internet access;
	•	a Discord Bot Token if Discord is enabled;
	•	a Telegram Bot Token if Telegram is enabled.
Python dependencies are installed from the root:
requirements.txt
Separate dependency files are not required for the current application architecture.
Quick Start
Clone the repository:
git clone https://github.com/Mafiodze/Castopia-bot.git
cd Castopia-bot
Create a virtual environment.
Linux/macOS
python3.12 -m venv .venv
source .venv/bin/activate
Windows
py -3.12 -m venv .venv
.venv\Scripts\activate
Install dependencies:
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Create the environment file:
cp .env.example .env
On Windows, create or copy .env manually if cp is not available.
Fill .env with the required tokens and configuration values.
Start Discord
python dsc/bot.py
Start Telegram
Run in a separate terminal:
python tg/bot.py
Start both processes
Linux/macOS:
./start.sh
Windows:
start.bat
For development, running Discord and Telegram in separate terminals is usually easier because their logs remain independent.
Environment Variables
Discord
DISCORD_BOT_TOKEN=...
Optional:
DISCORD_GUILD_ID=...
DISCORD_GUILD_ID can be used to synchronize application commands to a specific development guild.
Telegram
TELEGRAM_BOT_TOKEN=...
Wiki
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=CastopiaBot/2.0
WIKI_MAX_CONCURRENCY=4
WIKI_MAX_CONCURRENCY must remain within the supported range of 1..10.
WIKI_BASE_URL must be a valid HTTPS URL accepted by the project’s configuration validation.
Logging
LOG_LEVEL=INFO
Do not commit .env or real bot tokens.
Project Structure
Castopia-bot/
├── cogs/
│   ├── constants.py
│   ├── dsc.py
│   ├── page_parsing.py
│   ├── tg.py
│   └── txt_processing.py
├── dsc/
│   └── bot.py
├── tg/
│   └── bot.py
├── tests/
│   ├── test_discord_ui.py
│   └── test_wiki_client.py
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── DEPLOYMENT.md
├── LICENSE.txt
├── RAILWAY.md
├── README.md
├── SMOKE_TEST.md
├── railway.json
├── requirements.txt
├── runtime.txt
├── start.bat
└── start.sh
Historical deployment snapshots, local cache files, .pyc, __pycache__, and other generated runtime artifacts are not part of the intended working architecture.
Commands
Discord
Prefix commands:
.help
.search <title>
.randompage
.tags <tag> [tag...]
.fullsearch <text>
Slash commands:
/help
/search <title>
/randompage
/tags <tag>
/fullsearch <text>
Telegram
/start
/help
/search <title>
/randompage
/tags <tag> [tag...]
/fullsearch <text>
Testing
Run the test suite with:
python -m unittest discover -s tests -v
Run a compilation check with:
python -m compileall cogs dsc tg tests
The README intentionally does not claim a fixed number of passing tests. The current result must always be determined by running the test suite against the current codebase.
A successful compilation check does not prove that the bots work correctly at runtime.
Docker
The deployment architecture uses Python 3.12 and a slim Python base image.
Build the image:
docker build -t castopia-bot .
Run it:
docker run --env-file .env castopia-bot
The Docker image starts:
/app/start.sh
start.sh launches:
/app/dsc/bot.py
/app/tg/bot.py
and monitors the two processes.
Before using Docker, make sure secrets are not included in the Docker build context or image.
Docker Compose
The project provides:
docker-compose.yml
Start the local Compose deployment with:
docker compose up
The Compose configuration should remain consistent with:
Dockerfile
start.sh
requirements.txt
Do not assume that a Compose configuration works merely because the YAML file is valid. The container should still be tested at runtime.
Railway
Railway uses Docker deployment.
The deployment path is:
Railway
   ↓
railway.json
   ↓
Dockerfile
   ↓
./start.sh
   ├── dsc/bot.py
   └── tg/bot.py
        ↓
   shared WikiClient
The Railway deployment uses:
builder: DOCKERFILE
dockerfilePath: /Dockerfile
startCommand: ./start.sh
Procfile is not the current Railway startup mechanism.
For detailed deployment instructions, see:
	•	RAILWAY.md⁠
	•	DEPLOYMENT.md⁠
	•	SMOKE_TEST.md⁠
Deployment
The main deployment files are:
Dockerfile
docker-compose.yml
railway.json
start.sh
requirements.txt
runtime.txt
The deployment documentation is:
	•	Deployment Guide⁠
	•	Railway Deployment Guide⁠
	•	Smoke Test⁠
Smoke Test
After code changes or deployment, use:
SMOKE_TEST.md
At minimum, verify:
	•	Discord startup;
	•	Telegram startup;
	•	.search / /search;
	•	.randompage / /randompage;
	•	.tags / /tags;
	•	.fullsearch / /fullsearch;
	•	Discord autocomplete;
	•	Discord pagination;
	•	Telegram pagination;
	•	rate limiting;
	•	Wiki error handling;
	•	configuration validation;
	•	caching;
	•	concurrency.
Do not consider a deployment successful merely because a process starts or a hosting dashboard reports Running.
The application should be verified through its actual user-facing commands.
Configuration
The main configuration layer is shared between Discord and Telegram.
The intended flow is:
Environment
    ↓
cogs/constants.py
    ↓
WikiConfig
    ↓
WikiClient
    ↓
Discord / Telegram adapters
Configuration should be validated before the bot starts serving requests.
Caching
Caching is runtime application state.
Do not:
	•	commit cache.pkl;
	•	use repository cache files as persistent runtime storage;
	•	copy local cache state into production;
	•	rely on a cache file being present for startup.
Runtime cache should remain separate from repository source files.
Security
Never commit:
.env
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
API keys
cookies
session data
passwords
Do not store secrets in JSON, pickle, logs, source code, or deployment artifacts.
If a token has been exposed, revoke it and create a replacement.
Removing a secret from the latest commit does not remove it from Git history.
Wiki access controls must not be bypassed.
401 and 403 responses should be treated as access-denial responses, not as problems to circumvent.
Do not add mechanisms for bypassing:
	•	CAPTCHA;
	•	WAF;
	•	authentication;
	•	authorization;
	•	rate limits;
	•	other source-side access controls.
Wiki Errors
The Wiki client should handle upstream failures explicitly.
Relevant cases include:
401
403
404
429
5xx
timeout
connection errors
invalid HTML structure
missing required content
A change in Wiki HTML structure should result in a diagnostic parsing error rather than silently returning corrupted data.
Wiki parsing belongs in:
cogs/page_parsing.py
Do not duplicate Wiki selectors or parsing logic in Discord or Telegram adapters.
Rate Limiting and Concurrency
Discord commands use internal rate limiting.
Wiki requests use bounded concurrency controlled by:
WIKI_MAX_CONCURRENCY
Recommended default:
4
Supported configuration range:
1..10
Increasing concurrency does not automatically improve performance.
Excessive concurrency can increase load on the Wiki and lead to more 429 responses.
Source of Truth
For deployment:
Dockerfile
docker-compose.yml
start.sh
requirements.txt
railway.json
runtime.txt
For runtime:
dsc/bot.py
tg/bot.py
cogs/dsc.py
cogs/tg.py
cogs/page_parsing.py
cogs/constants.py
cogs/txt_processing.py
For tests:
tests/test_discord_ui.py
tests/test_wiki_client.py
For operational verification:
SMOKE_TEST.md
If documentation and the actual configuration disagree, the actual configuration takes precedence. Update the documentation after the runtime configuration changes.
Troubleshooting
Bot does not start
Check:
python --version
Python should be 3.12.
Check the installed dependencies:
python -c "import discord, aiogram, aiohttp, bs4, lxml; print('Dependencies OK')"
Check that .env exists and contains the required variables.
Do not print tokens while troubleshooting.
Discord commands do not appear
Check:
DISCORD_BOT_TOKEN
DISCORD_GUILD_ID
For global application commands, allow time for Discord command propagation.
For development, DISCORD_GUILD_ID can be used for guild-specific synchronization.
Telegram does not start
Check:
TELEGRAM_BOT_TOKEN
Also verify that another running process is not already polling with the same Telegram bot token.
Wiki returns 403
Treat this as access denial.
Do not add bypass logic.
Use an authorized API or access method.
Wiki returns 429
Check:
WIKI_MAX_CONCURRENCY
Review retry behavior and request frequency.
Do not blindly increase concurrency.
Wiki structure error
If the bot reports that the Wiki structure has changed, inspect:
cogs/page_parsing.py
and compare the parser selectors with the current HTML structure of the Wiki.
Do not patch the problem inside the Discord or Telegram adapters.
One bot stops while the other continues
The two bots run as separate processes.
Inspect the logs of the affected entry point:
dsc/bot.py
or:
tg/bot.py
Look for the first actual traceback rather than a later restart message.
Contributing
Before submitting a change:
python -m unittest discover -s tests -v
python -m compileall cogs dsc tg tests
Also verify:
	•	no secrets are committed;
	•	.env is not tracked;
	•	.pyc and __pycache__ are not tracked;
	•	runtime cache is not tracked;
	•	existing Discord commands remain available;
	•	existing Telegram commands remain available;
	•	the shared WikiClient architecture is preserved;
	•	no unnecessary architectural changes were introduced.
Do not change the project architecture simply to reduce the number of lines of code.
License
The Castopia Bot source code is licensed under the MIT License.
See:
LICENSE.txt
The MIT License applies to the project source code owned by the copyright holder.
Content retrieved from or displayed from the Castopia Wiki is subject to the licensing terms and rights of the Wiki and its respective rights holders.
The bot’s MIT License does not grant additional rights to:
	•	Wiki content;
	•	Wiki trademarks;
	•	logos;
	•	images;
	•	third-party text;
	•	other third-party materials.
Third-party libraries remain subject to their own licenses and terms.
Documentation
	•	Deployment Guide⁠
	•	Railway Deployment Guide⁠
	•	Smoke Test⁠