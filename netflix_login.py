#!/usr/bin/env python3
import os, sys, glob, shutil, json

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

FILES_CACHE = None

def find_cookies(force=False):
    global FILES_CACHE
    if FILES_CACHE and not force:
        return FILES_CACHE
    files = []
    for root, dirs, fs in os.walk(COOKIES_DIR):
        if root.endswith('good_cookies'):
            for f in sorted(fs):
                if f.endswith('.txt'):
                    files.append(os.path.join(root, f))
    FILES_CACHE = files
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

def open_brave(cookies):
    import subprocess, time, os, signal
    from playwright.sync_api import sync_playwright

    BRAVE = '/usr/bin/brave'
    PORT = 9222
    DATA_DIR = os.path.expanduser('~/.config/BraveSoftware/Brave-Browser')

    subprocess.run(['pkill', '-x', 'brave'], capture_output=True)
    time.sleep(1)
    subprocess.Popen(
        [BRAVE, f'--remote-debugging-port={PORT}', f'--user-data-dir={DATA_DIR}',
         '--no-first-run'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(60):
        try:
            import urllib.request
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=1)
            break
        except:
            time.sleep(1)
    else:
        print('  ❌ Brave did not start in time')
        return

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{PORT}')
        page = browser.new_page()
        page.context.clear_cookies()
        cdp = page.context.new_cdp_session(page)
        cdp.send('Network.setCookies', {'cookies': cookies})
        page.goto('https://www.netflix.com/browse', wait_until='domcontentloaded')
        page.close()

def build_alive_cookies(path):
    nfid, snfid = extract_ids(path)
    if not nfid:
        return None
    return [
        {'name': 'NetflixId', 'value': nfid,
         'url': 'https://www.netflix.com',
         'secure': True, 'httpOnly': True, 'sameSite': 'Lax'},
        {'name': 'SecureNetflixId', 'value': snfid or '',
         'url': 'https://www.netflix.com',
         'secure': True, 'httpOnly': True, 'sameSite': 'Lax'},
    ]

def main():
    print(BANNER)
    files = find_cookies()
    if not files:
        print('\n  ❌ No good_cookies found.')
        sys.exit(1)

    print(f'\n  Found {len(files)} accounts\n')

    for i, f in enumerate(files):
        email, plan, country = parse_meta(f)
        print(f'  {i+1:>2}. {email:35s} | {plan:15s} | {country}')

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

    if idx < 0 or idx >= len(files):
        print('  ❌ Invalid selection')
        sys.exit(1)

    selected = files[idx]
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
