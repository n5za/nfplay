
<br>

<div align="center">
  <h1>nfplay</h1>
  <p>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python">
    <img src="https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos%20%7C%20android-grey?style=flat-square">
  </p>
</div>

---
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/n5za/nfplay/blob/main/img/image.png">
  <img src="/img/image.png" alt="nfplay" width="100%">
</picture>

## Tools

### 🔍 cookie_password_checker.py
Scans Netflix cookie files and identifies accounts with **no password set**.

```
📊 Loaded 106 cookie files [Premium]
  ✓ #  1 GOOD  | user@gmail.com              | Premium | US
  [██████████████████████████████] 100%  ✔13  ✘93  💀0
```

- Batch scan hundreds of Netscape-format cookie files
- Color-coded terminal UI with real-time progress + ETA
- Detects `newPassword` without `currentPassword` → **GOOD**
- Sorted output: `good_no_password.txt`, `bad_has_password.txt`, `dead.txt`
- Filter by plan (Premium / Basic / Standard)
- Saves working cookie files to `good_cookies/` for instant use

```bash
pip install requests colorama
python cookie_password_checker.py              # interactive
python cookie_password_checker.py ./Cookies Premium  # direct
```

---
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/n5za/nfplay/blob/main/img/2.png">
  <img src="/img/2.png" alt="nfplay" width="100%">
### 🚀 netflix_login.py
Select a GOOD account and open it directly in Brave — **cookies injected automatically**.

```
  Found 10 accounts

   1. ramk.gym@gmail.com       | Premium | IN
   2. m25091410@gmail.com      | Premium | MX
   ...

  Select account: 1
  ✅ Cookie saved → ~/netflix_current.txt
  🚀 Opening Brave...
```

- Lists all password-free accounts neatly
- Saves cookie file to `~/netflix_current.txt` for CLI use
- `--open` launches Brave, injects cookies via CDP, opens Netflix

```bash
python netflix_login.py           # pick from menu
python netflix_login.py --open 1  # pick + launch
python netflix_login.py 2         # direct select
```

---

## How cookie_password_checker works

| Step | Action |
|------|--------|
| 1 | Parse each cookie file → extract `NetflixId` / `SecureNetflixId` |
| 2 | Authenticate to Netflix |
| 3 | Fetch `https://www.netflix.com/password` |
| 4 | Check for `newPassword` and `currentPassword` fields |
| 5 | **GOOD** → `newPassword` present, `currentPassword` absent |
| 6 | **BAD** → both present |

---

## Cookie format

```
.netflix.com	TRUE	/	TRUE	1798040804	NetflixId	v%3D3%26ct%3D...
.netflix.com	TRUE	/	TRUE	1798040804	SecureNetflixId	v%3D3%26mac%3D...
```

Files may include metadata in the filename:
```
[Premium] [1 payments] [extra false] [US] [user@gmail.com].txt
```

---

## Requirements

```txt
requests
colorama
```

For `netflix_login.py --open` only:
```txt
playwright
```

---

<div align="center">
  <sub>Built by <a href="https://github.com/n5za">n5za</a> · nfplay</sub>
</div>
