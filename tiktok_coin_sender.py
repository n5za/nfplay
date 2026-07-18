#!/usr/bin/env python3

import os, sys, re, json, time, glob, random, threading, atexit
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import md5
from urllib.parse import urlencode, urlparse

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except:
    class _C: RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'; CYAN='\033[96m'; MAGENTA='\033[95m'; RESET='\033[0m'
    Fore, Style = _C(), _C()

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    pass

CURL_AVAILABLE = False
try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except:
    pass

GIFTS = {
    'rose': 1, '1': 1, '5': 5, 'panda': 5, '10': 10, '15': 15,
    '20': 20, 'cake': 20, '30': 30, '50': 50, '99': 99,
    '100': 100, 'lion': 100, '500': 500, 'universe': 500,
}

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def colored(s, c): return f'{c}{s}{Style.RESET_ALL}'

def jdump(obj, limit=900):
    try:
        s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        s = str(obj)
    if len(s) > limit:
        return s[:limit] + '...'
    return s

def pick_room_data(sigi):
    if not isinstance(sigi, dict):
        return None

    candidates = []
    cr = sigi.get('CurrentRoom') or {}
    lr = sigi.get('LiveRoom') or {}
    candidates.extend([
        cr,
        cr.get('roomInfo') if isinstance(cr.get('roomInfo'), dict) else {},
        lr,
        lr.get('roomInfo') if isinstance(lr.get('roomInfo'), dict) else {},
    ])

    for src in candidates:
        if not isinstance(src, dict):
            continue
        room_id = src.get('roomId') or src.get('room_id') or src.get('id') or ''
        anchor_id = src.get('anchorId') or src.get('ownerId') or src.get('authorId') or ''
        name = src.get('anchorUniqueId') or src.get('uniqueId') or src.get('nickname') or src.get('nicknameStr') or ''
        if room_id or anchor_id or name:
            return {
                'roomId': room_id,
                'anchorId': anchor_id,
                'name': name,
                'sourceKeys': list(src.keys())[:30],
            }
    return None

def summarize_html(html, limit=40):
    try:
        ids = re.findall(r'<script[^>]+id=["\']([^"\']+)["\']', html or '', re.I)
        return ids[:limit]
    except Exception:
        return []

def parse_netscape(fpath):
    c = {}
    with open(fpath, encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('http') or line.startswith('-'):
                continue
            p = line.split('\t')
            if len(p) >= 7 and 'tiktok.com' in p[0]:
                c[p[5]] = p[6]
    return c

def parse_meta(fpath):
    meta = {}
    with open(fpath, encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if '\u2013' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    meta[parts[0].replace('\u2013', '').strip().lower()] = parts[1].strip()
    name = os.path.basename(fpath).replace('.txt', '')
    m = re.findall(r'\[(.*?)\]', name)
    if len(m) >= 9:
        meta['username'] = m[8].strip()
        try: meta['coins'] = str(int(m[3].replace(' coins', '').replace(',', '').strip()))
        except: pass
        meta['balance'] = m[4].strip()
        meta['country'] = m[7].strip()
        meta['followers'] = m[0].replace(' followers', '').strip()
    return meta

def list_accounts(folder, include_zero=False):
    files = sorted(glob.glob(os.path.join(folder, '*.txt')))
    accs = []
    for f in files:
        meta = parse_meta(f)
        try: coins = int(meta.get('coins', '0').replace(',', ''))
        except: coins = 0
        if coins == 0 and not include_zero: continue
        accs.append({
            'coins': coins, 'username': meta.get('username', '?'),
            'file': f, 'balance': meta.get('balance', '$0.00'),
            'country': meta.get('country', '??'),
            'followers': meta.get('followers', '?'),
        })
    return sorted(accs, key=lambda x: x['coins'], reverse=True)

# ─── Engine: Playwright + frontierSign ──────────────────
class PlaywrightEngine:
    def __init__(self):
        self._p = None
        self._browser = None
        self._ctx = None
        self._sign_page = None
        self._ready = False
        self._ua = user_agents[0]

    def start(self):
        if not PLAYWRIGHT_AVAILABLE:
            return False
        try:
            headless = os.environ.get('PW_HEADLESS', '0') == '1'
            self._p = sync_playwright().start()
            self._browser = self._p.chromium.launch(
                headless=headless, args=['--no-sandbox']
            )
            self._ctx = self._browser.new_context(
                user_agent=self._ua,
                viewport={'width': 1280, 'height': 720}
            )
            self._sign_page = self._ctx.new_page()
            self._sign_page.goto(
                'https://www.tiktok.com/',
                wait_until='domcontentloaded', timeout=20000
            )
            # Wait for byted_acrawler to load
            for _ in range(30):
                try:
                    ok = self._sign_page.evaluate('''(function() {
                        try { return !!(window.byted_acrawler && window.byted_acrawler.frontierSign); }
                        catch(e) { return false; }
                    })()''')
                    if ok:
                        self._ready = True
                        break
                except Exception:
                    pass
                time.sleep(1)
            return self._ready
        except Exception as e:
            print(colored(f' ⚠ Playwright init: {e}', Fore.YELLOW))
            return False

    def stop(self):
        try:
            if self._sign_page: self._sign_page.close()
            if self._ctx: self._ctx.close()
            if self._browser: self._browser.close()
            if self._p: self._p.stop()
        except: pass

    def set_cookies(self, cookies_dict):
        if not self._ctx: return
        cookies = [
            {'name': k, 'value': v, 'domain': '.tiktok.com', 'path': '/'}
            for k, v in cookies_dict.items()
        ]
        self._ctx.add_cookies(cookies)
        self._sign_page.goto(
            'https://www.tiktok.com/',
            wait_until='domcontentloaded', timeout=20000
        )
        time.sleep(3)
        # Re-check signer
        for _ in range(10):
            try:
                ok = self._sign_page.evaluate('''(function() {
                    try { return !!(window.byted_acrawler && window.byted_acrawler.frontierSign); }
                    catch(e) { return false; }
                })()''')
                if ok: break
            except Exception:
                pass
            time.sleep(1)

    def get_room_info(self, live_url):
        if not self._ready: return None
        page = self._ctx.new_page()
        try:
            page.goto(live_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)
            for _ in range(20):
                room = page.evaluate('''(function() {
                    try {
                        var s = window.SIGI_STATE || {};
                        var pick = function(src) {
                            if (!src) return null;
                            var roomId = src.roomId || src.room_id || src.id || '';
                            var anchorId = src.anchorId || src.ownerId || src.authorId || '';
                            var name = src.anchorUniqueId || src.uniqueId || src.nickname || src.nicknameStr || '';
                            if (!roomId && !anchorId && !name) return null;
                            return {roomId: roomId, anchorId: anchorId, name: name, keys: Object.keys(src).slice(0, 30)};
                        };
                        var cr = s.CurrentRoom || {};
                        var lr = s.LiveRoom || {};
                        return pick(cr) || pick(cr.roomInfo) || pick(lr) || pick(lr.roomInfo);
                    } catch(e) { return null; }
                })()''')
                if room and room.get('roomId'):
                    return room
                time.sleep(1)
            return None
        except:
            return None
        finally:
            try: page.close()
            except: pass

    def debug_room_probe(self, live_url):
        if not self._ready:
            return {'ok': False, 'msg': 'engine not ready'}
        page = self._ctx.new_page()
        requests_seen = []
        responses_seen = []

        def on_request(req):
            if len(requests_seen) < 40:
                requests_seen.append({
                    'method': req.method,
                    'resourceType': req.resource_type,
                    'url': req.url,
                })

        def on_response(resp):
            if len(responses_seen) < 20:
                responses_seen.append({
                    'status': resp.status,
                    'url': resp.url,
                })

        try:
            page.on('request', on_request)
            page.on('response', on_response)
            page.goto(live_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(6)
            html = ''
            try:
                html = page.content()
            except Exception:
                html = ''
            result = page.evaluate('''(function() {
                try {
                    var out = {
                        url: location.href,
                        title: document.title || '',
                        hasSigiState: !!window.SIGI_STATE,
                        sigiKeys: window.SIGI_STATE ? Object.keys(window.SIGI_STATE).slice(0, 20) : [],
                        currentRoom: null,
                        liveRoom: null,
                        roomInfo: null,
                        universalData: null,
                        htmlScripts: [],
                    };
                    if (window.SIGI_STATE && window.SIGI_STATE.CurrentRoom) {
                        var cr = window.SIGI_STATE.CurrentRoom;
                        out.currentRoom = {
                            roomId: cr.roomId || '',
                            anchorId: cr.anchorId || '',
                            anchorUniqueId: cr.anchorUniqueId || '',
                            liveRoomId: cr.liveRoomId || '',
                            roomInfo: cr.roomInfo || null,
                            keys: Object.keys(cr).slice(0, 30),
                        };
                        if (cr.roomInfo) {
                            out.roomInfo = {
                                keys: Object.keys(cr.roomInfo).slice(0, 20),
                                roomId: cr.roomInfo.roomId || cr.roomInfo.room_id || '',
                                ownerId: cr.roomInfo.ownerId || cr.roomInfo.owner_id || '',
                            };
                        }
                    }
                    if (window.SIGI_STATE && window.SIGI_STATE.LiveRoom) {
                        var lr = window.SIGI_STATE.LiveRoom;
                        out.liveRoom = {
                            roomId: lr.roomId || '',
                            anchorId: lr.anchorId || '',
                            anchorUniqueId: lr.anchorUniqueId || '',
                            liveRoomId: lr.liveRoomId || '',
                            roomInfo: lr.roomInfo || null,
                            keys: Object.keys(lr).slice(0, 30),
                        };
                    }
                    // __UNIVERSAL_DATA_FOR_REHYDRATION__
                    try {
                        var ud = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                        if (ud) {
                            var d = JSON.parse(ud.textContent);
                            var scope = d.__DEFAULT_SCOPE__ || {};
                            var appCtx = scope['webapp.app-context'] || {};
                            var bizCtx = scope['webapp.biz-context'] || {};
                            var user = appCtx.user || {};
                            out.universalData = {
                                hasCsrf: !!appCtx.csrfToken,
                                uid: user.uid || '',
                                uniqueId: user.uniqueId || '',
                                nickName: user.nickName || '',
                                hasLivePermission: !!user.hasLivePermission,
                                userRoomId: user.roomId || '',
                                region: user.region || '',
                                appContextKeys: Object.keys(appCtx).slice(0, 20),
                                bizContextKeys: Object.keys(bizCtx).slice(0, 20),
                            };
                        }
                    } catch(e) { out.universalData = {error: e.message}; }

                    out.htmlScripts = Array.from(document.querySelectorAll('script[id]')).slice(0, 40).map(function(s) {
                        return s.id;
                    });
                    return out;
                } catch(e) {
                    return {ok: false, msg: e.message};
                }
            })()''')
            result['html_len'] = len(html)
            result['html_script_ids'] = summarize_html(html)
            result['requests'] = requests_seen
            result['responses'] = responses_seen
            return result
        except Exception as e:
            return {'ok': False, 'msg': str(e)}
        finally:
            try: page.close()
            except: pass

    def get_live_recommendations(self, count=20):
        if not self._ready: return []
        try:
            return self._sign_page.evaluate('''(async function(count) {
                try {
                    var url = 'https://www.tiktok.com/api/recommend/item_list/?aid=1988&app_language=en&count=' + count + '&from_page=live&page_source=live_discover';
                    var sig = await window.byted_acrawler.frontierSign(url);
                    var su = url + '&X-Bogus=' + encodeURIComponent(sig['X-Bogus']);
                    var resp = await fetch(su, {credentials: 'include'});
                    var data = await resp.json();
                    var items = data.itemList || [];
                    return items.map(function(item) {
                        var a = item.author || {};
                        return {
                            roomId: item.roomId,
                            id: item.id,
                            authorId: a.id || a.uid,
                            authorName: a.uniqueId,
                        };
                    }).filter(function(i) { return i.roomId && i.authorName; });
                } catch(e) { return []; }
            })()''', count)
        except:
            return []

    def send_gift(self, room_id, owner_id, gift_id=1, gift_num=1):
        if not self._ready:
            return {'ok': False, 'msg': 'engine not ready'}
        try:
            return self._sign_page.evaluate('''(async function() {
                try {
                    var roomId = arguments[0], ownerId = arguments[1],
                        giftId = arguments[2], giftNum = arguments[3];
                    var c = document.cookie;
                    var g = function(n) { var m = c.match(new RegExp('(^| )' + n + '=([^;]+)')); return m ? m[2] : ''; };
                    var csrf = g('passport_csrf_token') || g('passport_csrf_token_default') || '';
                    var p = new URLSearchParams({
                        aid: '1988', room_id: roomId,
                        gift_id: String(giftId), gift_num: String(giftNum),
                        to_user_id: ownerId, type: 'live',
                    });
                    var url = 'https://www.tiktok.com/api/live/gift/send/?' + p.toString();
                    var sig = await window.byted_acrawler.frontierSign(url);
                    var su = url + '&X-Bogus=' + encodeURIComponent(sig['X-Bogus']);
                    var resp = await fetch(su, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRFToken': csrf,
                        },
                        body: p.toString(),
                        credentials: 'include',
                    });
                    var text = await resp.text();
                    var data;
                    try { data = JSON.parse(text); } catch(e) { data = {raw: text}; }
                    var sc = data.status_code !== undefined ? data.status_code : (data.code !== undefined ? data.code : -1);
                    var msg = data.status_msg || data.msg || '';
                    if (sc === 0 && !msg.includes('url')) {
                        return {ok: true, data: data};
                    }
                    return {ok: false, code: sc, msg: msg, data: data};
                } catch(e) {
                    return {ok: false, msg: e.message};
                }
            })()''', room_id, owner_id, gift_id, gift_num)
        except Exception as e:
            return {'ok': False, 'msg': str(e)}

    def get_csrf(self):
        if not self._ready: return ''
        try:
            return self._sign_page.evaluate('''(function() {
                var c = document.cookie;
                var m = c.match(/passport_csrf_token=([^;]+)/);
                return m ? m[1] : '';
            })()''')
        except:
            return ''

# ─── Engine: curl_cffi + X-Bogus (fallback) ────────────
class XBogus:
    sa = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe"
    magic = 536919696

    @staticmethod
    def md5x2(s): return md5(md5(s.encode()).digest()).hexdigest()
    @staticmethod
    def rc4(pt, key):
        s = list(range(256)); idx = 0
        for i in range(256):
            idx = (idx + s[i] + key[i % len(key)]) % 256
            s[i], s[idx] = s[idx], s[i]
        i = idx = 0; ct = ""
        for c in pt:
            i = (i + 1) % 256
            idx = (idx + s[i]) % 256
            s[i], s[idx] = s[idx], s[i]
            ct += chr(ord(c) ^ s[(s[i] + s[idx]) % 256])
        return ct
    @staticmethod
    def b64e(st, kt="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="):
        ll = []
        for i in range(0, len(st), 3):
            try:
                n1, n2, n3 = ord(st[i]), ord(st[i+1]), ord(st[i+2])
                ll.extend([n1>>2, (3&n1)<<4|(n2>>4), ((15&n2)<<2)|(n3>>6), 63&n3])
            except:
                ll.extend([n1>>2, (3&n1)<<4|0, 64, 64])
        return "".join(kt[v] for v in ll)
    @staticmethod
    def flt(nl): return [nl[x-1] for x in [3,5,7,9,11,13,15,17,19,21,4,6,8,10,12,14,16,18,20]]
    @staticmethod
    def scr(*a): return "".join(chr(_) for _ in [a[0],a[10],a[1],a[11],a[2],a[12],a[3],a[13],a[4],a[14],a[5],a[15],a[6],a[16],a[7],a[17],a[8],a[18],a[9]])
    @staticmethod
    def chk(sl): c=64; [c:=c^x for x in sl[3:]]; return c
    @staticmethod
    def _xb(par, ua, ts, data=""):
        md = XBogus.md5x2(data); mp = XBogus.md5x2(par)
        mu = md5(XBogus.b64e(XBogus.rc4(ua,[0,1,14])).encode()).hexdigest()
        sl = [ts, XBogus.magic, 64, 0, 1, 14,
              bytes.fromhex(mp)[-2], bytes.fromhex(mp)[-1],
              bytes.fromhex(md)[-2], bytes.fromhex(md)[-1],
              bytes.fromhex(mu)[-2], bytes.fromhex(mu)[-1]]
        sl.extend([(ts>>i)&0xFF for i in range(24,-1,-8)])
        sl.extend([(sl[1]>>i)&0xFF for i in range(24,-1,-8)])
        sl.extend([XBogus.chk(sl), 255])
        nl = XBogus.flt(sl)
        rc = XBogus.rc4(XBogus.scr(*nl), [255])
        return XBogus.b64e("\x02\xff"+rc, XBogus.sa)
    @staticmethod
    def sign(url, ua):
        p = url.split('?',1)[1] if '?' in url else ''
        return url + '&X-Bogus=' + XBogus._xb(p, ua, int(time.time()))

class CurlEngine:
    def __init__(self):
        self._session = None
        self._ua = user_agents[0]

    def start(self):
        if not CURL_AVAILABLE:
            return False
        self._session = curl_requests.Session()
        return True

    def set_cookies(self, cookies_dict):
        if not self._session: return
        for n, v in cookies_dict.items():
            self._session.cookies.set(n, v, domain='.tiktok.com')

    def get_room_info(self, live_url):
        try:
            url = XBogus.sign(live_url + '?aid=1988', self._ua)
            r = self._session.get(url, headers={'User-Agent': self._ua, 'Referer': 'https://www.tiktok.com/'},
                                    impersonate='chrome120', timeout=15)
            html = r.text
            if len(html) < 2000: return None
            m = re.search(r'<script id="SIGI_STATE"[^>]*>({.*?})</script>', html, re.DOTALL)
            if m:
                sigi = json.loads(m.group(1))
                room = pick_room_data(sigi)
                if room and room.get('roomId'):
                    return room
            return None
        except:
            return None

    def debug_room_probe(self, live_url):
        try:
            url = XBogus.sign(live_url + '?aid=1988', self._ua)
            r = self._session.get(url, headers={'User-Agent': self._ua, 'Referer': 'https://www.tiktok.com/'},
                                    impersonate='chrome120', timeout=15)
            html = r.text or ''
            out = {
                'url': live_url,
                'final_url': getattr(r, 'url', ''),
                'status_code': getattr(r, 'status_code', None),
                'has_sigi_state': 'SIGI_STATE' in html,
                'current_room_present': 'CurrentRoom' in html,
                'html_len': len(html),
            }
            # __UNIVERSAL_DATA_FOR_REHYDRATION__ from HTML
            try:
                um = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>({.*?})</script>', html, re.DOTALL)
                if um:
                    ud = json.loads(um.group(1))
                    scope = ud.get('__DEFAULT_SCOPE__', {})
                    app_ctx = scope.get('webapp.app-context', {})
                    user = app_ctx.get('user', {})
                    out['universal_data'] = {
                        'has_csrf': bool(app_ctx.get('csrfToken')),
                        'uid': user.get('uid', ''),
                        'unique_id': user.get('uniqueId', ''),
                        'nick_name': user.get('nickName', ''),
                        'has_live_permission': user.get('hasLivePermission', False),
                        'user_room_id': user.get('roomId', ''),
                        'region': user.get('region', ''),
                    }
            except Exception as e:
                out['universal_data_error'] = str(e)
            m = re.search(r'<script id="SIGI_STATE"[^>]*>({.*?})</script>', html, re.DOTALL)
            if m:
                try:
                    sigi = json.loads(m.group(1))
                    cr = sigi.get('CurrentRoom', {})
                    lr = sigi.get('LiveRoom', {})
                    out['sigi_keys'] = list(sigi.keys())[:20]
                    out['current_room'] = {
                        'roomId': cr.get('roomId', ''),
                        'anchorId': cr.get('anchorId', ''),
                        'anchorUniqueId': cr.get('anchorUniqueId', ''),
                        'liveRoomId': cr.get('liveRoomId', ''),
                        'roomInfo': cr.get('roomInfo', None),
                        'keys': list(cr.keys())[:30],
                    }
                    out['live_room'] = {
                        'roomId': lr.get('roomId', ''),
                        'anchorId': lr.get('anchorId', ''),
                        'anchorUniqueId': lr.get('anchorUniqueId', ''),
                        'liveRoomId': lr.get('liveRoomId', ''),
                        'roomInfo': lr.get('roomInfo', None),
                        'keys': list(lr.keys())[:30],
                    }
                except Exception as e:
                    out['sigi_parse_error'] = str(e)
            return out
        except Exception as e:
            return {'ok': False, 'msg': str(e)}

    def send_gift(self, room_id, owner_id, gift_id=1, gift_num=1, live_url=''):
        try:
            params = urlencode({
                'aid': '1988', 'room_id': room_id, 'gift_id': str(gift_id),
                'gift_num': str(gift_num), 'to_user_id': owner_id, 'type': 'live',
            })
            signed = XBogus.sign('https://www.tiktok.com/api/live/gift/send/?' + params, self._ua)
            r = self._session.post(signed,
                headers={
                    'User-Agent': self._ua,
                    'Referer': live_url or 'https://www.tiktok.com/',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://www.tiktok.com',
                },
                data=params, impersonate='chrome120', timeout=15)
            j = r.json() if r.text else {}
            sc = j.get('status_code', j.get('code', -1))
            msg = j.get('status_msg', j.get('msg', ''))
            if sc == 0 and 'url' not in msg:
                return {'ok': True, 'data': j}
            return {'ok': False, 'code': sc, 'msg': msg, 'data': j}
        except Exception as e:
            return {'ok': False, 'msg': str(e)}

# ─── Main ───────────────────────────────────────────────
def main():
    print(Fore.CYAN + Style.BRIGHT + '''
  ╔══════════════════════════════════════╗
  ║     TikTok COIN SENDER v5            ║
  ║  Playwright + frontierSign + X-Bogus ║
  ║  --detect-only  --probe-log  --debug ║
  ╚══════════════════════════════════════╝
''' + Style.RESET_ALL)

    args = sys.argv[1:]
    COOKIES_DIR = None; LIVE_URL = None; COINS_TO_SEND = 1; GIFT_NAME = '1'
    NUM_ACCOUNTS = 1; RANDOM = False; LOOP = False; THREADS = 1
    MIN_C = 0; MAX_C = 999999; DELAY = 1.0; WATCH = False; AUTO = False; SAVE = False
    ENGINE = 'playwright'; DEBUG_ROOM = False; TRACE_NET = False; DETECT_ONLY = False; PROBE_LOG = ''

    i = 0
    while i < len(args):
        a = args[i]
        if a == '--url' and i+1 < len(args): LIVE_URL = args[i+1]; i+=1
        elif a == '--engine' and i+1 < len(args): ENGINE = args[i+1]; i+=1
        elif a == '--gift' and i+1 < len(args): GIFT_NAME = args[i+1].lower(); i+=1
        elif a == '--coins' and i+1 < len(args): COINS_TO_SEND = int(args[i+1]); i+=1
        elif a == '--count' and i+1 < len(args): NUM_ACCOUNTS = int(args[i+1]); i+=1
        elif a == '--all': NUM_ACCOUNTS = 999999
        elif a == '--threads' and i+1 < len(args): THREADS = int(args[i+1]); i+=1
        elif a == '--delay' and i+1 < len(args): DELAY = float(args[i+1]); i+=1
        elif a == '--min-coins' and i+1 < len(args): MIN_C = int(args[i+1]); i+=1
        elif a == '--max-coins' and i+1 < len(args): MAX_C = int(args[i+1]); i+=1
        elif a == '--random': RANDOM = True
        elif a == '--loop': LOOP = True
        elif a == '--watch': WATCH = True
        elif a == '--auto': AUTO = True
        elif a == '--save-log': SAVE = True
        elif a == '--debug-room': DEBUG_ROOM = True
        elif a == '--trace-net': TRACE_NET = True
        elif a == '--detect-only': DETECT_ONLY = True
        elif a == '--probe-log' and i+1 < len(args): PROBE_LOG = args[i+1]; i+=1
        elif a == '--curl': ENGINE = 'curl'
        elif a == '--pw': ENGINE = 'playwright'
        elif COOKIES_DIR is None: COOKIES_DIR = a
        i += 1

    if not COOKIES_DIR:
        for d in ['/home/nasa/netflix-checker/data/results-tiktok/tiktok_all/coins_cookies',
                   '/home/nasa/netflix-checker/data/results-tiktok/tiktok_all/good_cookies',
                   '/home/nasa/netflix-checker/data/tiktok_all']:
            if os.path.isdir(d) and glob.glob(os.path.join(d, '*.txt')):
                COOKIES_DIR = d; break
        else:
            COOKIES_DIR = input(colored('📁 Cookies folder: ', Fore.CYAN)).strip()

    accs = list_accounts(COOKIES_DIR)
    all_accs = list_accounts(COOKIES_DIR, True)
    print(f' {colored("📂", Fore.CYAN)} {len(all_accs)} total, {colored(len(accs), Fore.GREEN)} with coins')

    if not accs:
        print(colored(' ❌ No accounts with coins found', Fore.RED)); sys.exit(1)

    if not LIVE_URL:
        LIVE_URL = input(colored('🎥 Live URL (or press Enter to search): ', Fore.CYAN)).strip()

    gift_id = GIFTS.get(GIFT_NAME, 1)
    gift_cost = gift_id

    # Init engine
    engine = None
    if ENGINE == 'playwright' and PLAYWRIGHT_AVAILABLE:
        e = PlaywrightEngine()
        if e.start():
            engine = e
            print(colored(f' ✅ Playwright engine ready (frontierSign)', Fore.GREEN))
    if not engine and ENGINE == 'curl' and CURL_AVAILABLE:
        e = CurlEngine()
        if e.start():
            engine = e
            print(colored(f' ✅ curl_cffi engine ready (X-Bogus)', Fore.GREEN))

    if not engine:
        print(colored(f' ❌ No engine available. Install playwright or curl_cffi', Fore.RED))
        print(colored(f'    pip install playwright && playwright install chromium', Fore.YELLOW))
        sys.exit(1)

    # Set cookies from first usable account
    first_cookies = parse_netscape(accs[0]['file'])
    engine.set_cookies(first_cookies)
    print(colored(f' 🔑 Using @{accs[0]["username"]} ({accs[0]["coins"]} coins)', Fore.CYAN))

    # ─── DETECT-ONLY MODE ────────────────────────────
    if DETECT_ONLY:
        if not LIVE_URL or 'tiktok.com' not in LIVE_URL:
            print(colored(' ❌ --detect-only requires --url <live_url>', Fore.RED))
            engine.stop(); sys.exit(1)
        print(colored(f'\n 🔎 [DETECT-ONLY] Probing: {LIVE_URL}', Fore.CYAN))
        if hasattr(engine, 'debug_room_probe'):
            probe = engine.debug_room_probe(LIVE_URL)
            print(colored(f' 🧪 Full probe:', Fore.MAGENTA))
            print(colored(jdump(probe, 5000), Fore.MAGENTA))
            if PROBE_LOG:
                t = datetime.now().strftime('%Y%m%d_%H%M%S')
                pname = LIVE_URL.split('/@')[-1].split('/')[0] if '/@' in LIVE_URL else 'unknown'
                os.makedirs(PROBE_LOG, exist_ok=True)
                pf = os.path.join(PROBE_LOG, f'probe_{pname}_{t}.json')
                with open(pf, 'w') as f:
                    json.dump(probe, f, ensure_ascii=False, indent=2)
                print(colored(f' 💾 Probe saved: {pf}', Fore.GREEN))
            sys.exit(0)
        else:
            print(colored(f' ⚠ debug_room_probe not available', Fore.YELLOW))
            sys.exit(0)

    # Find room
    room_info = None
    if LIVE_URL and 'tiktok.com' in LIVE_URL:
        print(colored(f'\n 🔍 Checking room: {LIVE_URL}', Fore.YELLOW))
        room_info = engine.get_room_info(LIVE_URL)
        if room_info:
            print(colored(f' ✅ Live: @{room_info.get("name","?")} room={room_info["roomId"]}', Fore.GREEN))
        elif (DEBUG_ROOM or TRACE_NET) and hasattr(engine, 'debug_room_probe'):
            probe = engine.debug_room_probe(LIVE_URL)
            print(colored(f' 🧪 room probe: {jdump(probe)}', Fore.MAGENTA))
            if PROBE_LOG:
                t = datetime.now().strftime('%Y%m%d_%H%M%S')
                pname = LIVE_URL.split('/@')[-1].split('/')[0] if '/@' in LIVE_URL else 'unknown'
                os.makedirs(PROBE_LOG, exist_ok=True)
                pf = os.path.join(PROBE_LOG, f'probe_{pname}_{t}.json')
                with open(pf, 'w') as f:
                    json.dump(probe, f, ensure_ascii=False, indent=2)
                print(colored(f' 💾 Probe saved: {pf}', Fore.GREEN))

    # Search for live if no URL or room offline
    if not room_info:
        print(colored(f' 🔍 Searching for active lives...', Fore.YELLOW))
        recs = engine.get_live_recommendations(30) if hasattr(engine, 'get_live_recommendations') else []
        print(colored(f' 📡 Found {len(recs)} recommendations', Fore.CYAN))
        if DEBUG_ROOM or TRACE_NET:
            print(colored(f' 🧪 recommendations sample: {jdump(recs[:5])}', Fore.MAGENTA))

        if isinstance(engine, PlaywrightEngine):
            for rec in recs[:10]:
                rn = rec.get('authorName', '')
                if not rn: continue
                ul = f'https://www.tiktok.com/@{rn}/live'
                sys.stdout.write(f'\r    Checking @{rn}... ')
                sys.stdout.flush()
                ri = engine.get_room_info(ul)
                if ri and ri.get('roomId'):
                    room_info = ri
                    LIVE_URL = ul
                    print(colored(f'✅ {rn}', Fore.GREEN))
                    break
                print(colored(f'❌', Fore.RED))
                if (DEBUG_ROOM or TRACE_NET) and hasattr(engine, 'debug_room_probe'):
                    probe = engine.debug_room_probe(ul)
                    print(colored(f'    probe: {jdump(probe)}', Fore.MAGENTA))
                time.sleep(1)

    if not room_info:
        print(colored(f'\n ❌ No live rooms found. Try again later.', Fore.RED))
        engine.stop()
        sys.exit(1)

    print(colored(f'\n 🏠 Room: {room_info["roomId"]}', Fore.CYAN))
    print(colored(f' 👤 Host: @{room_info.get("name","?")} ({room_info["anchorId"]})', Fore.CYAN))

    # Filter usable accounts
    usable = [a for a in accs if MIN_C <= a['coins'] <= MAX_C and a['coins'] >= gift_cost]
    if RANDOM: random.shuffle(usable)

    if not usable:
        print(colored(f' ❌ No accounts meet criteria (min_coins={MIN_C}, need >= {gift_cost})', Fore.RED))
        engine.stop(); sys.exit(1)

    # ─── SEND ────────────────────────────────────────────
    total = min(NUM_ACCOUNTS, len(usable))
    if not AUTO:
        inp = input(colored(f'\n🚀 Send {COINS_TO_SEND} gift(s) from [{total}] accounts? (number): ', Fore.YELLOW)).strip()
        if inp and inp.isdigit(): total = min(int(inp), len(usable))

    print(colored(f'\n ▸ {total} accounts × {COINS_TO_SEND} gift(s)\n', Fore.CYAN))

    log = []; errors = []

    def send_one(acc):
        c = parse_netscape(acc['file'])
        engine.set_cookies(c)
        if isinstance(engine, PlaywrightEngine):
            time.sleep(0.5)
        return engine.send_gift(room_info['roomId'], room_info['anchorId'], gift_id, COINS_TO_SEND)

    if LOOP:
        sent = 0
        try:
            while True:
                for a in usable:
                    r = send_one(a)
                    if r['ok']:
                        sent += COINS_TO_SEND
                        print(colored(f'  ✅ @{a["username"]:<20} +{COINS_TO_SEND}  [total: {sent}]', Fore.GREEN))
                        log.append(r)
                    else:
                        print(colored(f'  ❌ @{a["username"]:<20} {r.get("msg","?")}', Fore.RED))
                        errors.append(r)
                    if DELAY > 0: time.sleep(DELAY)
                print(colored(f'\n 🔄 Round complete. {sent} gifts sent.\n', Fore.MAGENTA))
                time.sleep(2)
        except KeyboardInterrupt:
            print(colored(f'\n ⏹ Stopped. Sent: {sent}', Fore.YELLOW))
    else:
        success = 0
        if THREADS > 1 and total > 1 and isinstance(engine, CurlEngine):
            with ThreadPoolExecutor(max_workers=THREADS) as ex:
                fs = {ex.submit(send_one, a): a for a in usable[:total]}
                for f in as_completed(fs):
                    r = f.result()
                    if r['ok']:
                        success += COINS_TO_SEND
                        print(colored(f'  ✅ @{fs[f]["username"]:<20} +{COINS_TO_SEND}', Fore.GREEN))
                        log.append(r)
                    else:
                        print(colored(f'  ❌ @{fs[f]["username"]:<20} {r.get("msg","?")}', Fore.RED))
                        errors.append(r)
                    if DELAY > 0: time.sleep(DELAY)
        else:
            for idx, a in enumerate(usable[:total]):
                sys.stdout.write(f'\r    [{idx+1}/{total}] @{a["username"]} ({a["coins"]} coins)... ')
                sys.stdout.flush()
                r = send_one(a)
                if r['ok']:
                    success += COINS_TO_SEND
                    print(colored(f'✅', Fore.GREEN))
                    log.append({'user': a['username'], **r})
                else:
                    print(colored(f'❌ {r.get("msg","?")}', Fore.RED))
                    errors.append({'user': a['username'], **r})
                if DELAY > 0 and idx < total - 1: time.sleep(DELAY)

        print()
        print(colored(f' ═══════════════════════════════════════', Fore.CYAN))
        print(colored(f'  ✅ SENT     : {len(log)}/{total}', Fore.GREEN))
        print(colored(f'  💰 GIFTS    : {success}', Fore.GREEN))
        print(colored(f'  ❌ FAILED   : {len(errors)}', Fore.RED))
        print(colored(f'  🎯 LIVE     : {LIVE_URL}', Fore.CYAN))
        print(colored(f'  ═══════════════════════════════════════', Fore.CYAN))

        if SAVE:
            lf = f'/home/nasa/netflix-checker/data/send_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            with open(lf, 'w') as f:
                f.write(f'URL: {LIVE_URL}\nGifts: {COINS_TO_SEND}×{len(log)} = {success}\n\n')
                for r in log: f.write(f'OK  | {r.get("user","?")}\n')
                for r in errors: f.write(f'FAIL| {r.get("user","?")} | {r.get("msg","?")}\n')
            print(colored(f'  📄 Log: {lf}', Fore.CYAN))

    engine.stop()

if __name__ == '__main__':
    main()
