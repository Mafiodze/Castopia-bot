# Smoke Test Guide for Castopia Discord Bot

This guide helps validate the bot implementation after stabilization changes.

## Prerequisites

1. Discord bot is running and connected to a test guild
2. `.env` file configured with:
   - `DISCORD_BOT_TOKEN` - valid bot token
   - `WIKI_BASE_URL` - wiki source URL (e.g., https://castopia.site)
   - `WIKI_USER_AGENT` - bot user agent
   - `WIKI_MAX_CONCURRENCY` - max concurrent requests (e.g., 4)
   - `DISCORD_GUILD_ID` - optional test guild ID for syncing commands
   - `LOG_LEVEL` - logging level (e.g., INFO)

## Test Checklist

### 1. Bot Startup
- [ ] Bot connects to Discord Gateway without errors
- [ ] All cogs load successfully
- [ ] Slash commands are registered (global or in test guild)
- [ ] No critical errors in logs during startup

### 2. Prefix Commands (`.` prefix)

#### `.help`
- [ ] Command responds within 3 seconds
- [ ] Shows all 5 command descriptions
- [ ] Display is readable and formatted in Russian

#### `.search <title>`
- [ ] `.search Пример` finds an article by partial title match
- [ ] `.search unknown-article-xyz` returns "not found" message
- [ ] Response includes article title, URL, and excerpt
- [ ] Rate limit works: 3 requests per 20 seconds per user

#### `.randompage`
- [ ] Returns a random public article each time
- [ ] Skips system/draft articles
- [ ] Response includes article title, URL, and excerpt
- [ ] Rate limit works: 2 requests per 20 seconds per user

#### `.tags <tag1> [tag2...]`
- [ ] `.tags основное` returns articles with that tag
- [ ] Multiple tags work: `.tags тег1 тег2`
- [ ] Returns "not found" if no articles match
- [ ] Embeds show up to 20 results

#### `.fullsearch <query>`
- [ ] `.fullsearch поиск` finds articles containing that text
- [ ] Results sorted by relevance (title matches ranked higher)
- [ ] Pagination works: "← Назад" and "Вперёд →" buttons appear
- [ ] Only original requester can use pagination buttons
- [ ] Rate limit works: 1 request per 30 seconds per user

### 3. Slash Commands (`/`)

#### All slash commands
- [ ] Interaction is acknowledged within 3 seconds (deferred)
- [ ] "Thinking..." state appears while bot processes
- [ ] No "This interaction failed" Discord error
- [ ] Response appears as bot message (not in followup)

#### `/search` with Autocomplete
- [ ] Type `/search` and wait for autocomplete suggestions
- [ ] Suggestions appear after typing 2+ characters
- [ ] Suggestions match typed text
- [ ] Selecting suggestion works correctly

#### `/randompage`, `/tags`, `/fullsearch`
- [ ] Each works identically to prefix version
- [ ] Proper defer behavior (no 3-second timeout)
- [ ] Rate limits enforced (same as prefix commands)

#### Rate Limit Response
- [ ] Hitting rate limit shows: "Подождите X с перед следующим запросом."
- [ ] Message is ephemeral (only sender sees it) for slash commands
- [ ] Waiting timeout allows next request

### 4. Error Handling

#### Access Errors (403)
- [ ] Bot shows: "Источник запретил автоматический доступ..."
- [ ] No retry attempts logged for 403
- [ ] No CAPTCHA/WAF bypass attempts

#### Server Errors (429, 5xx)
- [ ] Bot retries up to 3 times
- [ ] Eventually shows: "Источник временно недоступен..."
- [ ] Logs show retry attempts

#### Content Structure Errors
- [ ] If wiki structure changes: "Структура источника изменилась..."
- [ ] Admin/draft articles excluded from results
- [ ] Empty search results show: "По запросу «...» ничего не найдено."

### 5. Concurrency & Caching

#### Concurrency Limits
- [ ] Multiple simultaneous `.fullsearch` requests don't crash bot
- [ ] Wiki queries show max 4 concurrent connections (check logs)
- [ ] No more than 4 articles loaded simultaneously

#### Caching Behavior
- [ ] First `.search <title>` query logs `cache_hit=false`
- [ ] Immediate repeat shows `cache_hit=true` in logs
- [ ] Cache TTL expires after configured time (5-10 minutes for lists)

#### Search Lock
- [ ] Only one fulltext search runs at a time
- [ ] Multiple `.fullsearch` requests queue properly (check logs for `wiki_search`)
- [ ] Results are cached for 5 minutes

### 6. Logging Validation

Check logs for structured format:
```
wiki_request status=200 duration_ms=... attempt=1 url=...
wiki_fetch cache_hit=true url=...
discord_command command=search mode=slash duration_ms=...
wiki_rate_allowed user_id=... command=search remaining=...
wiki_rate_limited user_id=... command=search wait_seconds=...
```

- [ ] No sensitive tokens logged
- [ ] Commands log with accurate duration
- [ ] Cache hits/misses tracked
- [ ] Rate limit decisions logged

### 7. Pagination & UI

#### Search Results View
- [ ] Results paginate at 5 per page
- [ ] "Результаты поиска" header shows "Найдено: N • страница X/Y"
- [ ] Navigation buttons show article title and excerpt
- [ ] Each article has clickable "[Открыть статью]" link
- [ ] Buttons disabled on first/last page appropriately

#### Russian Text
- [ ] All embeds use Russian language
- [ ] Special characters (Russian letters) display correctly
- [ ] No encoding errors in responses

### 8. Configuration

#### Optional Guild ID
If `DISCORD_GUILD_ID` is set:
- [ ] Commands synced to that specific guild only
- [ ] Appear in test guild instantly (no 1-hour delay)
- [ ] Still accessible to that guild members

If `DISCORD_GUILD_ID` is not set:
- [ ] Commands registered globally
- [ ] Available to all guilds after 1 hour
- [ ] Check logs for: "Synced X global application commands"

## Acceptance Criteria

✅ `.search` and `/search` find articles on current wiki  
✅ `.randompage`, `.tags`, `.fullsearch` use real article list (not empty)  
✅ Slash commands confirm interaction within 3 seconds  
✅ Bot makes max 4 wiki requests simultaneously  
✅ Telegram client still starts and imports wiki client without regressions  

## Common Issues & Troubleshooting

| Issue | Solution |
|-------|----------|
| Commands not appearing | Check logs for sync status, wait up to 1 hour for global |
| 3-second timeout error | Ensure slash command uses defer before operation |
| Empty search results | Check HTML parser logs, verify wiki structure |
| High concurrency errors | Reduce `WIKI_MAX_CONCURRENCY` in `.env` |
| No autocomplete | Run `/search` command, wait 2+ seconds after typing |
| Cache not working | Check TTL values in `WikiClient` constants (10 min default) |

