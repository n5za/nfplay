#!/usr/bin/env python3

import os, sys, re, json, time, html, urllib.parse, traceback, tempfile, zipfile, shutil
from datetime import datetime
from collections import OrderedDict

try:
    from colorama import Fore, Style, init; init(autoreset=True)
except:
    class _C: RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'; CYAN='\033[96m'; MAGENTA='\033[95m'; RESET='\033[0m'; DIM='\033[2m'; BRIGHT='\033[1m'
    Fore, Style = _C(), _C()

try:
    import requests
except:
    os.system('pip install requests --break-system-packages')

try:
    from telethon import TelegramClient
except:
    os.system('pip install telethon --break-system-packages')
    from telethon import TelegramClient

c = lambda s, x: f'{x}{s}{Style.RESET_ALL}'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TELEGRAM_CHANNELS = [
    '@freenetflixcookiesdaily',
    '@premiumcookiesdailyupdate',
    '@cookielogin',
    '@freecookiesdaily',
    '@freepremiumaccountsnow',
    '@dailywebcookies',
    '@netflix_cookie_vip',
    '@freenetflixcookie',
    '@Netflix_Cookies_now',
]

# ── Pastebin Search ──────────────────────────────────────────

def search_pastebin_latest(limit=30):
    """Get recent public pastes from Pastebin archive"""
    url = 'https://pastebin.com/archive'
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=15)
        if r.status_code != 200: return []
        ids = set()
        for m in re.finditer(r'href="/([a-zA-Z0-9]{8})\?source=archive"', r.text):
            pid = m.group(1)
            if re.match(r'^[a-zA-Z0-9]{8}$', pid):
                ids.add(pid)
        return list(ids)[:limit]
    except: return []

def search_pastebin_playwright(query, limit=15):
    """Search pastebin via Playwright (bypasses Cloudflare)"""
    try:
        from playwright.sync_api import sync_playwright
    except:
        return []
    
    ids = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            page = ctx.new_page()
            page.goto(f'https://pastebin.com/search?q={urllib.parse.quote(query)}', wait_until='domcontentloaded', timeout=30000)
            
            import time as _time
            try:
                _time.sleep(3)
            except: pass
            
            html = page.content()
            for m in re.finditer(r'href="/([a-zA-Z0-9]{8})(?:\?|/|"|\s|$)', html):
                pid = m.group(1)
                if re.match(r'^[a-zA-Z0-9]{8}$', pid):
                    ids.add(pid)
            for m in re.finditer(r'pastebin\.com/([a-zA-Z0-9]{8})(?:\?|/|"|\s|$)', html):
                pid = m.group(1)
                if re.match(r'^[a-zA-Z0-9]{8}$', pid):
                    ids.add(pid)
            
            ctx.close(); browser.close()
    except:
        pass
    
    return list(ids)[:limit]

def fetch_raw_paste(paste_id):
    """Fetch raw content of a paste"""
    for url in [
        f'https://pastebin.com/raw/{paste_id}',
    ]:
        try:
            r = requests.get(url,
                             headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                             timeout=15)
            if r.status_code == 200 and len(r.text) > 20:
                return r.text
        except: pass
    return None

# ── Cookie Parsers ───────────────────────────────────────────

def detect_format(text):
    """Detect cookie format: 'json', 'netscape', or 'unknown'"""
    if not text or len(text) < 20: return 'unknown'
    t = text.strip()
    if (t.startswith('[') and ('"domain"' in t or '"name"' in t)) or \
       (t.startswith('{') and ('domain' in t and 'name' in t)):
        return 'json'
    if re.search(r'\.(netflix|spotify|tiktok)\.com\s+TRUE', t, re.IGNORECASE) or \
       re.search(r'\.(netflix|spotify|tiktok)\.com\s+/', t):
        return 'netscape'
    return 'unknown'

def parse_json_cookies(text):
    """Parse JSON cookie format -> list of {domain, name, value}"""
    try:
        data = json.loads(text)
        if isinstance(data, dict): data = [data]
        cookies = []
        for item in data:
            if isinstance(item, dict) and 'name' in item and 'value' in item:
                domain = item.get('domain', '').lstrip('.')
                cookies.append({
                    'domain': domain or '.netflix.com',
                    'name': item['name'],
                    'value': item['value'],
                })
        return cookies
    except: return []

def parse_netscape_cookies(text):
    """Parse Netscape cookie format -> list of {domain, name, value}"""
    cookies = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('http'): continue
        p = line.split('\t')
        if len(p) >= 7:
            domain = p[0].lstrip('.')
            name = p[5]
            value = p[6]
            cookies.append({'domain': domain, 'name': name, 'value': value})
    return cookies

def classify_service(cookies):
    """Classify which service these cookies belong to"""
    names = [c['name'] for c in cookies]
    all_vals = ' '.join(names).lower()
    
    netflix_keys = ['netflixid', 'securenfid', 'securenfapp', 'netflix']
    spotify_keys = ['sp_dc', 'sp_t', 'sp_key']
    tiktok_keys = ['sessionid', 'sid_tt', 'sid_guard', 'uid_tt', 'passport_auth']
    google_keys = ['__secure-3psid', '__secure-3papisid', 'sid', 'hsid', 'ssid']
    
    scores = {'Netflix': 0, 'Spotify': 0, 'TikTok': 0, 'Google': 0}
    
    for n in names:
        nl = n.lower()
        if any(k in nl for k in netflix_keys): scores['Netflix'] += 2
        if any(k in nl for k in spotify_keys): scores['Spotify'] += 2
        if any(k in nl for k in tiktok_keys): scores['TikTok'] += 2
        if any(k in nl for k in google_keys): scores['Google'] += 2
    
    max_score = max(scores.values())
    if max_score > 0:
        best = [s for s, sc in scores.items() if sc == max_score]
        return best[0]
    
    if any(c['domain'].endswith('.netflix.com') for c in cookies): return 'Netflix'
    if any('spotify.com' in c['domain'] for c in cookies): return 'Spotify'
    if any('tiktok.com' in c['domain'] for c in cookies): return 'TikTok'
    return 'Unknown'

def cookies_to_netscape(cookies_list, include_extra=True):
    """Convert cookie list to Netscape format string"""
    lines = [
        '# Netscape HTTP Cookie File',
        '# https://curl.se/rfc/cookie_spec.html',
        '# This file was generated by cookie_scraper.py',
        f'# Generated: {datetime.now().isoformat()}',
    ]
    
    # Sort by domain
    key_cookies = {c['name']: c for c in cookies_list}
    
    required = {
        'Netflix': ['NetflixId', 'SecureNetflixId'],
        'Spotify': ['sp_dc', 'sp_t'],
        'TikTok': ['sessionid', 'sid_tt'],
        'Google': ['__Secure-3PSID', '__Secure-3PAPISID'],
    }
    
    service = classify_service(cookies_list)
    needed = required.get(service, [])
    
    # Put required cookies first
    for n in needed:
        if n in key_cookies:
            ck = key_cookies[n]
            domain = ck.get('domain', '')
            if not domain.startswith('.'): domain = '.' + domain
            lines.append(f'{domain}\tTRUE\t/\tTRUE\t0\t{ck["name"]}\t{ck["value"]}')
    
    # Add rest
    if include_extra:
        for name, ck in key_cookies.items():
            if name not in needed:
                domain = ck.get('domain', '')
                if not domain.startswith('.'): domain = '.' + domain
                lines.append(f'{domain}\tTRUE\t/\tTRUE\t0\t{ck["name"]}\t{ck["value"]}')
    
    return '\n'.join(lines)

# ── Dedicated Cookie Site Scrapers ─────────────────────────────

def _extract_cookies_from_html(html_text):
    """Extract cookies from HTML — checks script/pre/text blocks"""
    cookies = []
    # 1. Script tags with JSON
    for m in re.finditer(r'<script[^>]*>([\s\S]*?)</script>', html_text):
        text = m.group(1).strip()
        if text.startswith('[') and 'domain' in text and 'name' in text:
            parsed = parse_json_cookies(text)
            if parsed:
                return parsed
    # 2. Pre/code blocks
    for m in re.finditer(r'<(pre|code)[^>]*>([\s\S]*?)</\1>', html_text):
        text = html.unescape(m.group(2).strip())
        fmt = detect_format(text)
        if fmt == 'json':
            parsed = parse_json_cookies(text)
            if parsed:
                return parsed
        elif fmt == 'netscape':
            parsed = parse_netscape_cookies(text)
            if parsed:
                return parsed
    # 3. JSON arrays in plain text
    for m in re.finditer(r'\[\s*\{[^}]*"domain"[^}]*"name"[^}]*"value"[^}]*\}\s*\]', html_text):
        parsed = parse_json_cookies(m.group(0))
        if parsed:
            return parsed
    # 4. Netscape blocks
    for m in re.finditer(r'(?:# Netscape|# https://curl)', html_text):
        start = max(0, m.start() - 50)
        block = html_text[start:m.end() + 1000]
        fmt = detect_format(block)
        if fmt == 'netscape':
            parsed = parse_netscape_cookies(block)
            if parsed:
                return parsed
    return cookies

def scrape_trickswire():
    """Scrape trickswire.com for Netflix cookies"""
    all_cookies = []
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    try:
        r = session.get('https://trickswire.com/netflix-cookies/', timeout=15)
        if r.status_code != 200:
            return []
        # Find sub-page links: /working-netflix-cookies-N/
        sub_pages = set(re.findall(r'/working-netflix-cookies-(\d+)/', r.text))
        for num in sorted(sub_pages, key=int):
            url = f'https://trickswire.com/working-netflix-cookies-{num}/'
            try:
                sub = session.get(url, timeout=15)
                if sub.status_code == 200:
                    cookies = _extract_cookies_from_html(sub.text)
                    all_cookies.extend(cookies)
            except:
                continue
        return all_cookies
    except:
        return []

def scrape_cookiesceo():
    """Scrape cookiesceo.com for Netflix/Spotify cookies"""
    cookies = []
    for url in ['https://cookiesceo.com/netflix-cookies/', 'https://cookiesceo.com/spotify-cookies/']:
        try:
            r = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=15
            )
            if r.status_code == 200:
                found = _extract_cookies_from_html(r.text)
                cookies.extend(found)
        except:
            pass
    return cookies

def scrape_dailynetflixcookies():
    """Scrape dailynetflixcookies.in for Netflix/Spotify/TikTok cookies"""
    cookies = []
    try:
        r = requests.get(
            'https://dailynetflixcookies.in/',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=15
        )
        if r.status_code == 200:
            found = _extract_cookies_from_html(r.text)
            cookies.extend(found)
    except:
        pass
    return cookies

# ── Filename Builder ─────────────────────────────────────────

def build_filename(paste_id, service, cookies_list, ext='txt'):
    """Build a descriptive filename for the cookie file"""
    names = [c['name'] for c in cookies_list]
    plan = ''
    email = ''
    country = ''
    try:
        # Try to extract email from filename if available
        pass
    except: pass
    
    plan_tag = f'[{plan}]' if plan else ''
    email_tag = f'[{email}]' if email else ''
    country_tag = f'[{country}]' if country else ''
    
    # Truncate paste id + service + date
    dt = datetime.now().strftime('%Y%m%d')
    base = f'{paste_id}_{service}_{dt}'
    return f'{base}.{ext}'

# ── Main App ─────────────────────────────────────────────────

SERVICE_QUERIES = {
    'Netflix': ['netflix cookies 2026', 'netflix cookie fresh 2026', 'netflix premium cookies 2026'],
    'Spotify': ['spotify cookies 2026', 'spotify cookie fresh 2026', 'spotify premium cookies 2026'],
    'TikTok': ['tiktok cookies 2026', 'tiktok session cookies 2026', 'tiktok cookie fresh 2026'],
}

def extract_paste_ids(query, limit_per_source=10):
    """Extract paste IDs from Pastebin search via Playwright"""
    all_ids = []
    
    try:
        ids = search_pastebin_playwright(query, limit=limit_per_source)
        for pid in ids:
            if pid and len(pid) == 8 and pid not in all_ids:
                all_ids.append(pid)
    except: pass
    
    return all_ids[:limit_per_source]

def extract_latest_pastes(limit=40):
    """Get latest pastes from archive"""
    return search_pastebin_latest(limit=limit)

class CookieScraper:
    def __init__(self):
        self.found = {}  # {paste_id: {service, cookies, raw, format}}
        self.results = {}
    
    def scan(self, max_ids_per_query=10):
        """Scan all queries and find cookie pastes"""
        print(f'\n{c("🔍 Scanning for fresh cookies...", Fore.CYAN)}\n')
        
        all_paste_ids = []
        seen_pids = set()
        
        # Source 1: Pastebin search via Playwright for each service
        for service, queries in SERVICE_QUERIES.items():
            for q in queries:
                print(f'  {c("🔍", Fore.CYAN)} Searching pastebin | {service:8s} | "{q[:45]:45s}"...', end=' ')
                ids = extract_paste_ids(q, limit_per_source=max_ids_per_query)
                for pid in ids:
                    if pid not in seen_pids:
                        seen_pids.add(pid)
                        all_paste_ids.append((pid, service))
                print(f'{len(ids)} IDs')
        
        # Source 2: Latest pastes from archive (check for cookie content)
        latest_ids = extract_latest_pastes(limit=30)
        print(f'  {c("📋", Fore.CYAN)} Pastebin archive → {len(latest_ids)} recent pastes')
        
        for pid in latest_ids:
            if pid not in seen_pids:
                seen_pids.add(pid)
                all_paste_ids.append((pid, None))  # no suggested service, will detect
        
        print(f'\n  {c("📥", Fore.CYAN)} Total unique IDs: {len(all_paste_ids)}')
        
        # Source 3: Dedicated cookie websites
        self.scan_dedicated_sites()
        
        # Source 4: Telegram channels
        self.scan_telegram()
        
        # Fetch and parse each paste
        seen_fetched = set()
        for paste_id, suggested_service in all_paste_ids:
            if paste_id in seen_fetched: continue
            seen_fetched.add(paste_id)
            
            sys.stdout.write(f'\r  {c("⏳", Fore.YELLOW)} Fetching {paste_id}... ')
            sys.stdout.flush()
            
            raw = fetch_raw_paste(paste_id)
            if not raw or len(raw) < 30:
                sys.stdout.write(f'\r  {c("⏭", Fore.YELLOW)} {paste_id} empty/unavailable\n')
                continue
            
            fmt = detect_format(raw)
            if fmt == 'unknown':
                sys.stdout.write(f'\r  {c("⏭", Fore.YELLOW)} {paste_id} unknown format\n')
                continue
            
            cookies = []
            if fmt == 'json':
                cookies = parse_json_cookies(raw)
            elif fmt == 'netscape':
                cookies = parse_netscape_cookies(raw)
            
            if not cookies:
                sys.stdout.write(f'\r  {c("⏭", Fore.YELLOW)} {paste_id} no valid cookies\n')
                continue
            
            service = classify_service(cookies)
            if service == 'Unknown':
                sys.stdout.write(f'\r  {c("⏭", Fore.YELLOW)} {paste_id} unknown service\n')
                continue
            
            self.found[paste_id] = {
                'service': service,
                'cookies': cookies,
                'raw': raw,
                'format': fmt,
                'suggested': suggested_service,
                'count': len(cookies),
            }
            sys.stdout.write(f'\r  {c("✅", Fore.GREEN)} {paste_id} | {service:8s} | {len(cookies):3d} cookies\n')
            time.sleep(1.5)  # be gentle to pastebin
        
        return self.found
    
    def scan_dedicated_sites(self):
        """Scan dedicated cookie websites for fresh cookies"""
        print(f'\n{c("🌐 Scanning dedicated cookie sites...", Fore.CYAN)}\n')
        
        scrapers = [
            ('trickswire', scrape_trickswire, 'TricksWire'),
            ('cookiesceo', scrape_cookiesceo, 'CookiesCEO'),
            ('dailynetflixcookies', scrape_dailynetflixcookies, 'DailyNetflixCookies'),
        ]
        
        for name, func, label in scrapers:
            print(f'  {c("🌐", Fore.CYAN)} Fetching {label}...', end=' ')
            try:
                cookies = func()
                if cookies:
                    service = classify_service(cookies)
                    source_key = f'{name}_{len(self.found) + 1}'
                    self.found[source_key] = {
                        'service': service,
                        'cookies': cookies,
                        'raw': '',
                        'format': 'json' if all('name' in c for c in cookies) else 'netscape',
                        'suggested': service,
                        'count': len(cookies),
                        'source': label,
                    }
                    print(f'{c(f"✅ {service} ({len(cookies)} cookies)", Fore.GREEN)}')
                else:
                    print(f'{c("⏭ no cookies found", Fore.YELLOW)}')
            except Exception as e:
                print(f'{c(f"❌ error: {e}", Fore.RED)}')
        
        return self.found
    
    def scan_telegram(self):
        """Scan Telegram channels for cookie pastes using Telethon"""
        print(f'\n{c("📱 Scanning Telegram channels via Telethon API...", Fore.CYAN)}\n')

        import asyncio

        cred_dir = os.path.expanduser('~/.config/cookie_scraper')
        cred_file = os.path.join(cred_dir, 'tg_credentials.json')
        session_path = os.path.join(cred_dir, 'tg_session.session')
        os.makedirs(cred_dir, exist_ok=True)

        if os.path.exists(cred_file):
            try:
                with open(cred_file) as f:
                    creds = json.load(f)
                api_id = creds['api_id']
                api_hash = creds['api_hash']
                phone = creds['phone']
            except Exception:
                api_id = api_hash = phone = None
        else:
            api_id = api_hash = phone = None

        if not api_id:
            print(f'  {c("Telegram API credentials needed.", Fore.YELLOW)}')
            print(f'  {c("Get them at https://my.telegram.org/apps", Style.DIM)}')
            api_id = input(f'  {c("api_id: ", Fore.CYAN)}').strip()
            api_hash = input(f'  {c("api_hash: ", Fore.CYAN)}').strip()
            phone = input(f'  {c("Phone (with country code, e.g. +1234567890): ", Fore.CYAN)}').strip()
            with open(cred_file, 'w') as f:
                json.dump({'api_id': int(api_id), 'api_hash': api_hash, 'phone': phone}, f)
            print(f'  {c("Credentials saved.", Fore.GREEN)}')

        async def scrape_channels():
            from telethon import TelegramClient
            from telethon.errors import SessionPasswordNeededError

            client = TelegramClient(session_path, int(api_id), api_hash)

            try:
                await client.start(phone=phone)
            except SessionPasswordNeededError:
                pwd = input(f'  {c("Two-factor auth code: ", Fore.YELLOW)}').strip()
                await client.sign_in(phone=phone, password=pwd)
            except Exception as e:
                code = input(f'  {c(f"Verification code sent to {phone}: ", Fore.YELLOW)}').strip()
                await client.sign_in(code=code)

            found_any = False

            for channel_username in TELEGRAM_CHANNELS:
                try:
                    entity = await client.get_entity(channel_username)
                    print(f'  {c("📱", Fore.CYAN)} Scanning {channel_username}...')

                    messages = await client.get_messages(entity, limit=50)

                    for msg in messages:
                        if not msg:
                            continue

                        text = msg.text or ''
                        channel_source = f'Telegram {channel_username}'

                        if text:
                            fmt = detect_format(text)
                            if fmt != 'unknown':
                                cookies = []
                                if fmt == 'json':
                                    cookies = parse_json_cookies(text)
                                elif fmt == 'netscape':
                                    cookies = parse_netscape_cookies(text)

                                if cookies:
                                    service = classify_service(cookies)
                                    source_key = f'tg_{channel_username[1:]}_{msg.id}'
                                    self.found[source_key] = {
                                        'service': service,
                                        'cookies': cookies,
                                        'raw': text,
                                        'format': fmt,
                                        'suggested': service,
                                        'count': len(cookies),
                                        'source': channel_source,
                                    }
                                    print(f'  {c("✅", Fore.GREEN)} {channel_source} msg {msg.id} | {service:8s} | {len(cookies):3d} cookies')
                                    found_any = True
                                    continue

                        if text:
                            for m in re.finditer(r'pastebin\.com/([a-zA-Z0-9]{8})', text):
                                pid = m.group(1)
                                if pid not in self.found:
                                    raw = fetch_raw_paste(pid)
                                    if raw and len(raw) > 30:
                                        fmt = detect_format(raw)
                                        if fmt != 'unknown':
                                            cookies = []
                                            if fmt == 'json':
                                                cookies = parse_json_cookies(raw)
                                            elif fmt == 'netscape':
                                                cookies = parse_netscape_cookies(raw)

                                            if cookies:
                                                service = classify_service(cookies)
                                                self.found[pid] = {
                                                    'service': service,
                                                    'cookies': cookies,
                                                    'raw': raw,
                                                    'format': fmt,
                                                    'suggested': service,
                                                    'count': len(cookies),
                                                    'source': channel_source,
                                                }
                                                print(f'  {c("✅", Fore.GREEN)} {channel_source} pastebin {pid} | {service:8s} | {len(cookies):3d} cookies')
                                                found_any = True

                        if msg.file and msg.file.name and msg.file.name.lower().endswith('.zip'):
                            tmp_dir = None
                            try:
                                tmp_dir = tempfile.mkdtemp(prefix='tg_cookies_')
                                zip_path = os.path.join(tmp_dir, msg.file.name)

                                await client.download_media(msg, file=zip_path)

                                with zipfile.ZipFile(zip_path, 'r') as zf:
                                    for fname in zf.namelist():
                                        if fname.lower().endswith('.txt'):
                                            content = zf.read(fname).decode('utf-8', errors='replace')
                                            fmt = detect_format(content)
                                            if fmt != 'unknown':
                                                cookies = []
                                                if fmt == 'json':
                                                    cookies = parse_json_cookies(content)
                                                elif fmt == 'netscape':
                                                    cookies = parse_netscape_cookies(content)

                                                if cookies:
                                                    service = classify_service(cookies)
                                                    source_key = f'tg_{channel_username[1:]}_{msg.id}_{fname}'
                                                    self.found[source_key] = {
                                                        'service': service,
                                                        'cookies': cookies,
                                                        'raw': content,
                                                        'format': fmt,
                                                        'suggested': service,
                                                        'count': len(cookies),
                                                        'source': channel_source,
                                                    }
                                                    print(f'  {c("📦", Fore.GREEN)} {channel_source} msg {msg.id} ({msg.file.name}/{fname}) | {service:8s} | {len(cookies):3d} cookies')
                                                    found_any = True
                            except Exception as e:
                                print(f'  {c(f"Warning: zip error in {channel_username}: {e}", Fore.YELLOW)}')
                            finally:
                                if tmp_dir:
                                    shutil.rmtree(tmp_dir, ignore_errors=True)

                except Exception as e:
                    print(f'  {c(f"Error scanning {channel_username}: {e}", Fore.RED)}')
                    traceback.print_exc()

            if not found_any:
                print(f'  {c("No cookies found in Telegram channels", Fore.YELLOW)}')

            await client.disconnect()

        try:
            asyncio.run(scrape_channels())
        except Exception as e:
            print(f'  {c(f"Telegram scan error: {e}", Fore.RED)}')
            traceback.print_exc()

        return self.found
    
    def list_cookies(self):
        """Display found cookies grouped by service"""
        grouped = {}
        for pid, info in self.found.items():
            svc = info['service']
            if svc not in grouped: grouped[svc] = []
            grouped[svc].append((pid, info))
        
        print(f'\n{c("═" * 60, Fore.CYAN)}')
        print(f'  {c("📋 AVAILABLE COOKIES", Style.BRIGHT + Fore.GREEN)}')
        print(f'{c("═" * 60, Fore.CYAN)}')
        
        service_colors = {'Netflix': Fore.RED, 'Spotify': Fore.GREEN, 'TikTok': Fore.MAGENTA, 'Google': Fore.BLUE}
        service_icons = {'Netflix': '🎬', 'Spotify': '🎵', 'TikTok': '📱', 'Google': '🔍'}
        
        idx = 1
        self.item_list = []
        
        for svc in ['Netflix', 'Spotify', 'TikTok', 'Google']:
            if svc not in grouped: continue
            color = service_colors.get(svc, Fore.WHITE)
            icon = service_icons.get(svc, '❓')
            items = grouped[svc]
            
            print(f'\n  {c(f"{icon} {svc} ({len(items)} pastes)", color)}')
            print(f'  {c("─" * 56, Style.DIM)}')
            
            for pid, info in items:
                netscape = cookies_to_netscape(info['cookies'], include_extra=False)
                netscape_full = cookies_to_netscape(info['cookies'], include_extra=True)
                key_names = [c['name'] for c in info['cookies']]
                
                # Detect plan
                all_text = ' '.join(key_names) + ' ' + info['raw'][:500]
                plan = '?'
                if 'Premium' in info['raw'][:2000] or 'premium' in info['raw'][:2000].lower():
                    m = re.search(r'(Premium\s+\w+)', info['raw'])
                    if m: plan = m.group(1)
                    else: plan = 'Premium'
                
                self.item_list.append({
                    'id': idx,
                    'paste_id': pid,
                    'service': svc,
                    'cookies': info['cookies'],
                    'netscape': netscape,
                    'netscape_full': netscape_full,
                    'plan': plan,
                    'count': len(info['cookies']),
                    'key_cookies': ', '.join(key_names[:8]),
                })
                
                keys_preview = ', '.join(key_names[:6])
                if len(key_names) > 6: keys_preview += '...'
                
                print(f'  {c(f"[{idx}]", Fore.YELLOW)} {c(pid, Fore.CYAN)} | {c(plan, Fore.YELLOW):15s} | {len(info["cookies"])} cookies | {keys_preview}')
                idx += 1
        
        self._print_legend()
        return self.item_list
    
    def _print_legend(self):
        print(f'\n  {c("─" * 56, Style.DIM)}')
        print(f'  {c("n:", Fore.YELLOW)} pick number · {c("a:", Fore.YELLOW)} all · {c("q:", Fore.YELLOW)} quit')
    
    def _shorten(self, text, max_len=60):
        return text[:max_len] + '...' if len(text) > max_len else text
    
    def download(self, selected_ids, check_after=False, output_dir=None):
        """Download selected cookies to files"""
        if output_dir is None:
            output_dir = os.path.join(BASE_DIR, 'data')
        
        downloaded = []
        for item in self.item_list:
            if item['id'] not in selected_ids: continue
            
            svc = item['service']
            svc_dir = os.path.join(output_dir, f'{svc.lower()}_harvested')
            os.makedirs(svc_dir, exist_ok=True)
            
            # Save Netscape cookie file
            dt = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{svc}_{item["paste_id"]}_{dt}.txt'
            fpath = os.path.join(svc_dir, filename)
            
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(item['netscape_full'])
            
            downloaded.append(fpath)
            print(c(f'    ✓ Saved: {filename}', Fore.GREEN))
        
        return downloaded

def run_checkers(file_paths):
    """Run the appropriate checker for each downloaded cookie file"""
    checkers = {
        'netflix': 'cookie_password_checker.py',
        'spotify': 'spotify_family_inviter.py',
        'tiktok': 'tiktok_cookie_checker.py',
    }
    
    results = []
    for fpath in file_paths:
        dirname = os.path.dirname(fpath)
        basename = os.path.basename(dirname)
        service = basename.replace('_harvested', '').lower()
        
        if service in checkers:
            checker = os.path.join(BASE_DIR, checkers[service])
            if os.path.isfile(checker):
                print(f'\n  {c(f"▶ Running {checkers[service]} on {fpath}...", Fore.CYAN)}')
                cmd = f'python3 "{checker}" "{fpath}" --no-save'
                # We'll just show the command for now
                results.append({'service': service, 'file': fpath, 'checker': checkers[service], 'cmd': cmd})
    
    return results

def main():
    print(Fore.CYAN + Style.BRIGHT + '''
  ╔══════════════════════════════════════╗
  ║     Cookie Harvester v1              ║
  ║  Pastebin Scanner · Daily Fresh Picks║
  ╚══════════════════════════════════════╝
''' + Style.RESET_ALL)
    
    args = sys.argv[1:]
    AUTO_MODE = False; INTERVAL = 21600
    CHECK_AFTER = False; OUTPUT_DIR = None
    
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--auto' or a == '--daemon': AUTO_MODE = True
        elif a == '--interval' and i+1 < len(args): INTERVAL = int(args[i+1]); i+=1
        elif a == '--check': CHECK_AFTER = True
        elif a == '--output' and i+1 < len(args): OUTPUT_DIR = args[i+1]; i+=1
        i += 1
    
    if OUTPUT_DIR is None:
        OUTPUT_DIR = os.path.join(BASE_DIR, 'data')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if AUTO_MODE:
        print(c(f'  🕐 Daemon mode — checking every {INTERVAL}s', Fore.YELLOW))
        os.makedirs(os.path.join(BASE_DIR, 'data', 'history'), exist_ok=True)
    
    while True:
        scraper = CookieScraper()
        found = scraper.scan(max_ids_per_query=10)
        
        if not found:
            print(f'\n  {c("😴 No fresh cookies found right now", Fore.YELLOW)}')
        else:
            items = scraper.list_cookies()
            print(f'\n  {c(f"Total: {len(found)} fresh pastes with cookies", Fore.GREEN)}')
            
            if not AUTO_MODE:
                choice = input(f'\n  {c("🎯 Pick numbers (e.g. 1-3,5,8) [a=all / q=quit]: ", Fore.YELLOW)}').strip().lower()
            else:
                choice = 'a'
            
            if choice == 'q': break
            elif choice == 'a':
                selected = [item['id'] for item in items]
            else:
                selected = set()
                for part in choice.replace(' ', '').split(','):
                    if not part: continue
                    if '-' in part:
                        try:
                            a, b = part.split('-')
                            for x in range(int(a), int(b)+1):
                                selected.add(x)
                        except: pass
                    else:
                        try: selected.add(int(part))
                        except: pass
            
            if selected:
                downloaded = scraper.download(selected, output_dir=OUTPUT_DIR)
                print(f'\n  {c(f"✅ Downloaded {len(downloaded)} cookie files", Fore.GREEN)}')
                
                if CHECK_AFTER and downloaded:
                    check_results = run_checkers(downloaded)
                    for cr in check_results:
                        ch = cr['checker']
                        fl = os.path.basename(cr['file'])
                        cm = cr['cmd']
                        print(f'  {c(f"■ {ch} ← {fl}", Fore.CYAN)}')
                        print(f'    {c(f"$ {cm}", Style.DIM)}')
        
        if not AUTO_MODE: break
        
        next_run = datetime.fromtimestamp(time.time() + INTERVAL).strftime('%H:%M:%S')
        print(f'\n  {c(f"💤 Next scan at {next_run}", Style.DIM)}')
        
        # Save history
        history_file = os.path.join(BASE_DIR, 'data', 'history', f'scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(history_file, 'w') as f:
            json.dump({'found': len(found), 'time': datetime.now().isoformat()}, f)
        
        time.sleep(INTERVAL)

if __name__ == '__main__':
    import time
    main()
