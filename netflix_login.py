#!/usr/bin/env python3
import os, sys, glob

COOKIES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'results-password')
OUTPUT_FILE = os.path.expanduser('~/netflix_current.txt')

def banner():
    print(r'''
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
                       Netflix Login''')

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
    parts = name.split('] [')
    email = parts[-1].rstrip(']') if parts else '?'
    plan = parts[0].lstrip('[') if parts else '?'
    country = parts[-2] if len(parts) >= 2 else '?'
    return email, plan, country

def extract_ids(path):
    nfid = snfid = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('.netflix.com'):
                parts = [p.strip() for p in line.split('\t')]
                if len(parts) >= 7:
                    name, val = parts[5], parts[6]
                    if name == 'NetflixId':
                        nfid = val
                    elif name == 'SecureNetflixId':
                        snfid = val
    return nfid, snfid

def main():
    banner()
    files = find_cookies()
    if not files:
        print('❌ No good_cookies found.')
        sys.exit(1)

    print(f'\n  Found {len(files)} accounts\n')

    for i, f in enumerate(files):
        email, plan, country = parse_meta(f)
        print(f'  {i+1:>2}. {email:35s} | {plan:15s} | {country}')

    idx = 0
    if len(sys.argv) > 1:
        try:
            idx = int(sys.argv[1]) - 1
        except:
            pass
    else:
        print()
        choice = input('  Select account: ').strip()
        try:
            idx = int(choice) - 1
        except:
            pass

    if idx < 0 or idx >= len(files):
        print('❌ Invalid selection')
        sys.exit(1)

    selected = files[idx]
    email, plan, country = parse_meta(selected)
    nfid, snfid = extract_ids(selected)

    import shutil
    shutil.copy2(selected, OUTPUT_FILE)

    print(f'\n✅ Cookie saved → {OUTPUT_FILE}')
    if nfid:
        print(f'📋 NetflixId:       {nfid}')
    if snfid:
        print(f'📋 SecureNetflixId: {snfid}')
    print(f'\n   Account: {email}')
    print(f'   Plan: {plan} | Country: {country}')

if __name__ == '__main__':
    main()
