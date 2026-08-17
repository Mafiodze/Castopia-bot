# Castopia bot

Telegram i Discord bot do wyszukiwania w **publicznej** wiki Castopia. Wspólna warstwa HTTP używa ograniczonej współbieżności, timeoutów, krótkiego cache w pamięci i kontrolowanych ponowień przy błędach `429` oraz `5xx`.

Bot nie omija CAPTCHA, WAF ani innych ograniczeń dostępu. Gdy serwis zwróci `401` lub `403`, należy użyć jego oficjalnego API albo uzyskać zgodę właściciela na automatyczny dostęp.

## Uruchomienie

1. Zainstaluj Python 3.11 lub nowszy i zależności:

   ```powershell
   py -m pip install -r requirements.txt
   ```

2. Skopiuj `.env.example` do `.env` i wpisz właściwy token Telegrama i/lub Discorda. Plik `.env` jest sekretem — nie publikuj go ani nie commituj.

3. Uruchom wybrany adapter z katalogu głównego projektu:

   ```powershell
   py -m tg.bot
   py -m dsc.bot
   ```

## Konfiguracja

| Zmienna | Znaczenie |
| --- | --- |
| `WIKI_BASE_URL` | HTTPS URL publicznego źródła (domyślnie `https://castopia.site`) |
| `WIKI_MAX_CONCURRENCY` | Liczba równoległych żądań do źródła, 1–10 (domyślnie 4) |
| `WIKI_USER_AGENT` | Jawna identyfikacja bota oraz kontakt do właściciela |
| `DISCORD_GUILD_ID` | Opcjonalny identyfikator serwera testowego do natychmiastowej synchronizacji slash-komend |
| `LOG_LEVEL` | Poziom logów, np. `INFO` lub `DEBUG` |

## Komendy

- Telegram: `/search`, `/fullsearch`, `/tags`, `/randompage`, `/help`
- Discord: `.search`, `.fullsearch`, `.tags`, `.randompage`, `.help` oraz odpowiadające im slash-komendy

Pełnotekstowe wyszukiwanie może chwilę potrwać przy pierwszym wywołaniu, ponieważ indeksuje publiczne strony. Kolejne wywołania korzystają z cache przez 10 minut.
