"""重启自检：切换数据目录后点「重启」，新进程必须还能正常打开界面。

单文件打包的程序靠环境变量携带解包目录，重启时若不清理，新进程会沿用旧进程那份
已被删除的临时目录，界面就只剩一行 not found。这个脚本专门守这个回归。

用法：python dev/dev_restart_check.py [exe 路径]
"""
import ctypes, json, os, re, subprocess, sys, time, urllib.request
from ctypes import wintypes
from pathlib import Path

EXE = sys.argv[1] if len(sys.argv) > 1 else str(
    Path(__file__).resolve().parent.parent / "dist" / "实用工具.exe")
NAME = os.path.basename(EXE)
WORK = os.path.join(os.path.dirname(os.path.abspath(EXE)), "_restart_check")
k32 = ctypes.windll.kernel32

class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

def snapshot():
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    e = PE32(); e.dwSize = ctypes.sizeof(PE32)
    out = {}
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        out[e.th32ProcessID] = (e.szExeFile, e.th32ParentProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return out

def ports_for(pids):
    txt = subprocess.run(["netstat","-ano"], capture_output=True, text=True, errors="replace").stdout
    res = {}
    for line in txt.splitlines():
        if "LISTENING" in line and "127.0.0.1:" in line:
            parts = line.split()
            if parts[-1].isdigit() and int(parts[-1]) in pids:
                res[int(parts[-1])] = int(parts[1].split(":")[-1])
    return res

for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","all_proxy","ALL_PROXY"):
    os.environ.pop(k, None)
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

for pid, (n, _) in snapshot().items():
    if n == NAME:
        subprocess.run(["taskkill","/PID",str(pid),"/F"], capture_output=True)
time.sleep(1)

before = set(snapshot())
subprocess.Popen([EXE])
port = None
for _ in range(40):
    time.sleep(1)
    new = {p: v for p, v in snapshot().items() if p not in before and v[0] == NAME}
    pp = ports_for(set(new))
    if pp:
        port = list(pp.values())[0]
        break
print("port", port)
assert port, "程序没有起来"

html = op.open(f"http://127.0.0.1:{port}/", timeout=10).read().decode("utf-8")
print("index:", [l.strip() for l in html.splitlines() if 'id="appVersion"' in l])
tok = re.search(r'window\.__TOKEN__="([^"]+)"', html).group(1)
def call(name, args=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/{name}",
        data=json.dumps({"args": args or []}).encode(),
        headers={"Content-Type":"application/json","X-Token":tok})
    return json.loads(op.open(req, timeout=60).read().decode("utf-8"))
b = call("bootstrap")
print("bootstrap:", {k: b.get(k) for k in ("ok","version","data_dir")})
print("set_dir:", call("data_set_dir", [os.path.join(WORK, "d2")]))
print("restart:", call("app_restart"))
time.sleep(6)
alive = {p: v for p, v in snapshot().items() if v[0] == NAME}
pp = ports_for(set(alive))
print("ports after:", pp)
ok = False
for p, prt in pp.items():
    try:
        r = op.open(f"http://127.0.0.1:{prt}/", timeout=10)
        body = r.read().decode("utf-8","replace")
        print(f"pid {p} port {prt} status={r.status} len={len(body)} has_app={'id=\"appVersion\"' in body}")
        ok = ok or (r.status == 200 and 'id="appVersion"' in body)
    except Exception as e:
        print("pid", p, "err", type(e).__name__, e)
print("RESTART_OK" if ok else "RESTART_FAIL")
for pid in list(alive):
    subprocess.run(["taskkill","/PID",str(pid),"/F"], capture_output=True)
sys.exit(0 if ok else 1)
