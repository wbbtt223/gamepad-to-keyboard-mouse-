# -*- coding: utf-8 -*-
"""重复启动保护测试：第二次启动应检测到已有实例并直接退出，不再开第二个。"""
import subprocess, sys, time, urllib.request

PY = sys.executable
PORT = 8807
URL = "http://127.0.0.1:%d" % PORT
ARGS = [PY, "gamepad_mapper.py", "--no-browser", "--port", str(PORT)]

fail = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  <- " + str(extra)))
    if not cond:
        fail.append(name)


p1 = subprocess.Popen(ARGS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    ok = False
    for _ in range(40):
        time.sleep(0.6)
        try:
            body = urllib.request.urlopen(URL + "/api/ping", timeout=1).read()
            if b"gamepad-mapper" in body:
                ok = True
                break
        except Exception:
            pass
    check("第一个实例已启动并可 ping", ok)

    t0 = time.time()
    r2 = subprocess.run(ARGS, capture_output=True, text=True, timeout=40)
    dt = time.time() - t0
    check("第二次启动立即退出", r2.returncode == 0 and dt < 25, "rc=%s dt=%.1fs" % (r2.returncode, dt))
    check("第二次启动提示已在运行", "已在运行" in r2.stdout, r2.stdout.strip()[:200])
    check("第二次启动没有开新面板端口", "控制台已启动" not in r2.stdout)
finally:
    try:
        req = urllib.request.Request(URL + "/api/cmd", data=b'{"cmd":"quit"}',
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as exc:
        print("(quit 失败: %r)" % exc)
    try:
        out = p1.communicate(timeout=25)[0]
        check("第一个实例正常退出", p1.returncode == 0, p1.returncode)
    except subprocess.TimeoutExpired:
        p1.kill()
        check("第一个实例正常退出", False, "超时")

print("-" * 46)
print("失败 %d 项" % len(fail), fail)
sys.exit(1 if fail else 0)
