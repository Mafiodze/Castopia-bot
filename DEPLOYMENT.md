Castopia Bot Deployment Guide
Castopia Bot consists of two bots that use a shared WikiClient:
Discord:
dsc/bot.py
    ↓
cogs/dsc.py
    ↓
cogs/page_parsing.py
    ↓
Castopia Wiki

Telegram:
tg/bot.py
    ↓
cogs/tg.py
    ↓
cogs/page_parsing.py
    ↓
Castopia Wiki
The architecture is intentionally simple: Discord and Telegram have separate entry points and adapters, while Wiki logic and configuration are shared.
1. Requirements
The following are required for local deployment:
	•	Python 3.12;
	•	pip;
	•	Internet access;
	•	a Discord Bot Token for Discord;
	•	a Telegram Bot Token for Telegram.
The project’s runtime image uses python:3.12-slim, so Python 3.12 is the current base version for deployment.
Dependencies are installed only from the root:
requirements.txt
The separate dsc/requirements.txt, tg/requirements.txt, and wkd/requirements.txt files are not independent dependency sources in the current architecture.
2. Environment Variables
Create .env based on .env.example.
Main variables:
Variable	Required	Purpose
DISCORD_BOT_TOKEN	Discord only	Discord bot token
TELEGRAM_BOT_TOKEN	Telegram only	Telegram bot token
WIKI_BASE_URL	No	HTTPS Wiki URL
WIKI_USER_AGENT	No	User-Agent for HTTP requests
WIKI_MAX_CONCURRENCY	No	Maximum Wiki request concurrency
DISCORD_GUILD_ID	No	Guild ID for development Discord command synchronization
LOG_LEVEL	No	Logging level
Current default values:
WIKI_BASE_URL=https://castopia.site
WIKI_MAX_CONCURRENCY=4
WIKI_BASE_URL must be an HTTPS URL without embedded credentials, query parameters, fragments, or an additional path.
Do not put real tokens in Git.
3. Local Installation
Clone the repository:
git clone https://github.com/Mafiodze/Castopia-bot.git
cd Castopia-bot
Create a virtual environment.
Linux/macOS:
python3.12 -m venv .venv
source .venv/bin/activate
Windows:
py -3.12 -m venv .venv
.venv\Scripts\activate
Install dependencies:
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Create .env:
cp .env.example .env
On Windows, the file can be created manually or copied using File Explorer.
Fill in the required tokens and configuration values.
4. Running Discord
Start:
python dsc/bot.py
Discord entry point:
dsc/bot.py
It loads cogs.dsc, creates the Discord bot, and synchronizes application commands.
For development, you can specify:
DISCORD_GUILD_ID=<guild id>
Application commands will then be synchronized to the specified guild.
Without DISCORD_GUILD_ID, global application commands are used.
5. Running Telegram
Run in a separate process:
python tg/bot.py
Telegram entry point:
tg/bot.py
It creates one WikiClient, passes it to create_router(), and starts polling.
6. Running Both Bots Locally
Linux/macOS:
./start.sh
Windows:
start.bat
For development, it is usually more convenient to run Discord and Telegram in separate terminals because this makes it easier to view their logs independently and stop one process without affecting the other.
start.sh starts both processes and monitors their state.
7. Tests
Before deployment, it is recommended to run:
python -m unittest discover -s tests -v
Compilation check:
python -m compileall cogs dsc tg tests
Do not document a fixed number of passing tests. The total number of tests can change as the codebase evolves.
8. Smoke Test
After startup, use:
SMOKE_TEST.md
At minimum, verify:
	•	Discord startup;
	•	Telegram startup;
	•	/search and .search;
	•	/randompage and .randompage;
	•	/tags and .tags;
	•	/fullsearch and .fullsearch;
	•	Discord autocomplete;
	•	Discord pagination;
	•	Telegram pagination;
	•	rate limiting;
	•	Wiki errors;
	•	cache behavior;
	•	configuration validation.
Do not consider the deployment successful simply because the process started. The bots must actually execute their main commands.
9. Docker
The current Docker deployment uses:
python:3.12-slim
and installs dependencies from:
requirements.txt
Build:
docker build -t castopia-bot .
Running the container requires the bot tokens and other environment variables.
Example:
docker run --env-file .env castopia-bot
The Dockerfile starts:
/app/start.sh
which is responsible for starting both bots.
Before using Docker, make sure .env is not included in the Docker image or Git repository.
10. Docker Compose
The project contains docker-compose.yml.
Make sure .env exists before starting:
docker compose up
Do not rely on old profiles or deployment modes unless they are actually present in the current Compose configuration.
Verify that the actual Compose behavior matches the current Dockerfile and start.sh.
Do not use Compose documentation as a substitute for actual runtime testing.
11. Railway
The current Railway configuration uses the Dockerfile:
builder: DOCKERFILE
dockerfilePath: /Dockerfile
and starts:
./start.sh
Therefore, the current Railway deployment should not be described as a Procfile-based deployment.
Main deployment properties:
	•	Docker build;
	•	one replica;
	•	./start.sh as the startup command;
	•	ON_FAILURE restart policy;
	•	a limited number of restart attempts.
Railway configuration is stored in:
railway.json
Railway Deployment
	1.	Create a Railway project.
	2.	Connect the GitHub repository.
	3.	Make sure Railway uses railway.json.
	4.	Add the required environment variables.
	5.	Deploy the project.
	6.	Check the Railway logs.
	7.	Run SMOKE_TEST.md after startup.
Environment variables:
DISCORD_BOT_TOKEN=...
TELEGRAM_BOT_TOKEN=...
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=CastopiaBot/2.0
WIKI_MAX_CONCURRENCY=4
LOG_LEVEL=INFO
Never publish the token values.
12. Railway Runtime Behavior
start.sh starts both processes:
python -u /app/dsc/bot.py
python -u /app/tg/bot.py
The script then monitors the processes and restarts a process if it exits.
Therefore, Railway treats the container as a single deployment containing two bot processes.
If one bot repeatedly crashes, first inspect its own traceback in the logs instead of blindly increasing the number of restart attempts.
13. Production Configuration
Recommended production configuration:
LOG_LEVEL=INFO
WIKI_MAX_CONCURRENCY=4
Change WIKI_MAX_CONCURRENCY only after checking Wiki behavior and load.
A higher value does not necessarily mean better performance. Excessive concurrency can place unnecessary load on the external source and increase the number of 429 responses.
14. Security
Never commit:
.env
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
API keys
cookies
session data
Runtime cache, __pycache__, .pyc, and other temporary artifacts must also not be stored in Git.
Before publishing changes, check:
git status
git ls-files
Make sure .env and runtime artifacts are not tracked.
If a token has ever been published, revoke it and create a new one. Simply deleting the line from the current commit does not remove the secret from Git history.
15. Deployment Troubleshooting
Discord starts, but commands do not appear
Check:
DISCORD_BOT_TOKEN
DISCORD_GUILD_ID
and the startup logs.
For global application commands, account for propagation delays.
Telegram does not start
Check:
TELEGRAM_BOT_TOKEN
and make sure another process is not already using the same bot token for polling.
Wiki returns 403
This means the source rejected the request.
Do not add bypass mechanisms for CAPTCHA, WAF, or access control.
Use the official API or an authorized access method.
Wiki returns 429
Check:
	•	WIKI_MAX_CONCURRENCY;
	•	retry logs;
	•	Retry-After;
	•	request frequency;
	•	cache behavior.
Wiki structure error
If the application reports that the source structure has changed, inspect the Wiki HTML and the corresponding selectors in:
cogs/page_parsing.py
Do not fix Wiki parsing in the Discord or Telegram adapters.
Wiki parsing must remain in cogs/page_parsing.py.
One bot crashes while the other continues running
Because both processes are started by start.sh, a failure of one process should not automatically mean that the other process is unavailable.
Check the traceback for the affected entry point:
dsc/bot.py
or:
tg/bot.py
16. Deployment Files
Main deployment files in the current architecture:
Dockerfile
docker-compose.yml
railway.json
start.sh
start.bat
runtime.txt
requirements.txt
Documentation:
DEPLOYMENT.md
RAILWAY.md
SMOKE_TEST.md
README.md
Do not treat historical deployment summaries or generated snapshots as part of the runtime configuration.
17. What Is Not a Runtime Dependency
The following artifacts must not be used as runtime sources:
cache.pkl
__pycache__/
*.pyc
Do not move runtime state into Git simply to speed up the next startup.
18. Verified vs. Unverified
Project documentation must not claim:
Production ready
20/20 tests passing
Both bots verified
Railway working
unless the corresponding checks were actually performed.
Use:
PASS
FAIL
NOT RUN
and provide a reason for NOT RUN.
19. Recommended Release Sequence
Before production deployment:
1. Install dependencies
2. Run unit tests
3. Run compilation check
4. Review changed files
5. Check secrets
6. Build Docker image
7. Start both bots
8. Run smoke tests
9. Deploy to Railway
10. Check production logs
11. Run production smoke test
If a smoke test finds an error, fix the code or configuration first and then repeat the verification.
Do not treat an automatic Railway restart as proof that the application is functioning correctly.
20. License
Wiki content and content displayed by the application are subject to the licensing terms stated by the source project and the configured footer.
Refer to the repository LICENSE.txt and the Wiki’s own licensing information for the applicable project and source terms.