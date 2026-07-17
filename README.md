# Netflix Cookie Password Checker

A Python tool that scans Netflix cookie files and identifies accounts without a password set. When an account has no password, the `/password` page shows `newPassword` and `confirmNewPassword` fields **without** a `currentPassword` field — meaning you can set a password without needing the old one.

## Features

- Batch scan hundreds of Netflix cookie files
- Colorful terminal UI with real-time progress
- Detects accounts with no password set (GOOD)
- Sorts results into `good_no_password.txt`, `bad_has_password.txt`, `dead.txt`
- Filter by plan (e.g. `Premium`, `Basic`, `Standard`)
- Resume-friendly output (append mode)

## Requirements

- Python 3.8+
- `requests` library
- `colorama` library

## Installation

### Windows

**Step 1 — Install Python**
Download and install Python from https://www.python.org/downloads/
**Make sure to check "Add Python to PATH" during installation.**

**Step 2 — Download the tool**
```
git clone https://github.com/n5za/nfplay.git
cd nfplay
```
Or download the ZIP from https://github.com/n5za/nfplay and extract it.

**Step 3 — Install dependencies**
Open **Command Prompt (cmd)** or **PowerShell** in the tool folder and run:
```
pip install requests colorama
```

**Step 4 — Run**
```
python cookie_password_checker.py
```

---

### Linux (Debian / Ubuntu / Mint)

**Step 1 — Install Python and Git**
Open **Terminal** and run:
```
sudo apt update
sudo apt install python3 python3-pip git -y
```

**Step 2 — Download the tool**
```
git clone https://github.com/n5za/nfplay.git
cd nfplay
```

**Step 3 — Install dependencies**
```
pip3 install requests colorama
```

**Step 4 — Run**
```
python3 cookie_password_checker.py
```

---

### Linux (Arch / Manjaro)

**Step 1 — Install Python and Git**
```
sudo pacman -S python python-pip git --noconfirm
```

**Step 2 — Download the tool**
```
git clone https://github.com/n5za/nfplay.git
cd nfplay
```

**Step 3 — Install dependencies**
```
pip install requests colorama
```

**Step 4 — Run**
```
python cookie_password_checker.py
```

---

### macOS

**Step 1 — Install Homebrew (if not already installed)**
Open **Terminal** and run:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Step 2 — Install Python and Git**
```
brew install python git
```

**Step 3 — Download the tool**
```
git clone https://github.com/n5za/nfplay.git
cd nfplay
```

**Step 4 — Install dependencies**
```
pip3 install requests colorama
```

**Step 5 — Run**
```
python3 cookie_password_checker.py
```

---

### Termux (Android)

**Step 1 — Install dependencies**
Open **Termux** and run:
```
pkg update && pkg upgrade -y
pkg install python git -y
```

**Step 2 — Download the tool**
```
git clone https://github.com/n5za/nfplay.git
cd nfplay
```

**Step 3 — Install dependencies**
```
pip install requests colorama
```

**Step 4 — Run**
```
python cookie_password_checker.py
```

---

## Usage

Run the tool:
```bash
python cookie_password_checker.py
```
(Use `python3` instead of `python` on Linux/macOS if `python` is not found.)

You'll be prompted to enter the cookies folder path:

```
📁 Enter cookies folder path:
  > /path/to/cookies
```

Or pass it as an argument:

```bash
python3 cookie_password_checker.py /path/to/cookies
```

### Arguments

| Argument | Description |
|----------|-------------|
| `arg1`   | Path to folder containing `.txt` cookie files |
| `arg2`   | Filter keyword (e.g. `Premium`, `Basic`) — use `__all__` for all |
| `arg3`   | Output directory (default: `./data/results-password`) |

### Examples

```bash
# Scan all accounts
python3 cookie_password_checker.py ./Cookies __all__ ./results

# Scan only Premium accounts
python3 cookie_password_checker.py ./Cookies Premium

# Custom output
python3 cookie_password_checker.py ./Cookies Premium ./my-results
```

## Cookie File Format

The tool expects Netscape-format cookie files containing `NetflixId` and optionally `SecureNetflixId`:

```
.netflix.com	TRUE	/	TRUE	1798040804	NetflixId	v%3D3%26ct%3D...
.netflix.com	TRUE	/	TRUE	1798040804	SecureNetflixId	v%3D3%26mac%3D...
```

File names like `[Premium] [1 payments] [extra false] [US] [user@gmail.com].txt` are parsed for plan, payment count, and country metadata.

## How It Works

1. Reads each cookie file and extracts `NetflixId` / `SecureNetflixId`
2. Authenticates to Netflix using the cookies
3. Visits `https://www.netflix.com/password`
4. Checks the page JSON for `newPassword` and `currentPassword` fields
5. **GOOD** = `newPassword` present, `currentPassword` absent (no password set)
6. **BAD** = both present (account has a password)

## Output

```
    ╔══════════════════════════════════════════════╗
    ║          NETFLIX COOKIE CHECKER v1.0         ║
    ║           Password Status Scanner             ║
    ╚══════════════════════════════════════════════╝

📊 Loaded 106 cookie files [Premium]
  ✓ #  1 GOOD  | user@gmail.com                   | Premium | US
  [██████████████████████████████] 100%  [106/106]  ✔13  ✘93  💀0  !0

  ✅ CHECK COMPLETE
  ✔ GOOD (no password) : 13
  ✘ BAD (has password) : 93
  ⏱ Time              : 171s (2.8min)
```

## Notes

- For educational purposes only
- Rate-limited by Netflix (approx. 35-40 checks/min)
- Use responsibly
