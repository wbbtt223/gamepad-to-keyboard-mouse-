# -*- coding: utf-8 -*-
"""语音输入真机验证（走真实 InputSimulator，即程序内部真正用的那条路径）。

两步：
  1) 发 Win+R，看「运行」对话框是否弹出 —— 验证 Win 键的注入方式对不对。
     （Win 键如果注入方式错了，系统会完全收不到，这一步就会失败。）
  2) 运行框本身就是文本输入框，在里面发 Win+H，看听写面板是否出现。
     注意：Win+H 在没有输入焦点的地方是**不会有反应**的，这是系统行为。
"""
import ctypes
import ctypes.wintypes as wt
import io
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import gamepad_mapper as G

user32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
VK_ESC = 0x1B


def snap():
    out = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _lp):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            t = ctypes.create_unicode_buffer(n + 2)
            user32.GetWindowTextW(hwnd, t, n + 2)
            c = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, c, 256)
            out[int(hwnd)] = (t.value, c.value)
        return True

    user32.EnumWindows(cb, 0)
    return out


def proc_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return "?"
    buf = ctypes.create_unicode_buffer(600)
    sz = wt.DWORD(600)
    k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
    k32.CloseHandle(h)
    return os.path.basename(buf.value)


def runbox(table):
    for h, (t, c) in table.items():
        if c == "#32770" and ("运行" in t or t == "Run"):
            return h
    return None


def esc():
    if IS_WIN:
        for _ in range(2):
            IS_WIN.key_tap(VK_ESC)
            time.sleep(0.3)


IS_WIN = G.InputSimulator()
if not IS_WIN.enabled:
    print("SendInput 不可用")
    sys.exit(2)

print("=" * 70)
print("第 1 步：Win+R 是否能真的调出「运行」对话框（验证 Win 键注入方式）")
print("=" * 70)
esc()
base = snap()
IS_WIN.combo_tap("win+r")
time.sleep(1.6)
after = snap()
box = runbox(after)
if box:
    print("PASS  Win 键注入正确：运行对话框已弹出（hwnd=%d）" % box)
else:
    print("FAIL  没弹出运行对话框。Win 键注入方式有问题，语音输入也不会生效。")
    print("      新出现的窗口：")
    for h in set(after) - set(base):
        print("        %r %r %s" % (after[h][0], after[h][1], proc_of(h)))
    sys.exit(1)

print()
print("=" * 70)
print("第 2 步：在真正的文本编辑框（记事本）里发 Win+H")
print("=" * 70)
import subprocess

esc()
try:
    note = subprocess.Popen(["notepad.exe"])
except Exception as exc:
    print("启动记事本失败：%r" % (exc,))
    sys.exit(1)
time.sleep(3.5)


def find_notepad():
    for h in snap():
        if proc_of(h).lower().startswith("notepad"):
            return h
    return None


def force_foreground(hwnd):
    """把窗口抢到前台。后台进程直接 SetForegroundWindow 会被系统拒绝，
    先模拟一次 ALT 按下可以解除这个前台锁定。"""
    user32.ShowWindow(hwnd, 9)                      # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    if user32.GetForegroundWindow() == hwnd:
        return True
    IS_WIN.key_down(G.VK_TABLE["alt"])
    user32.SetForegroundWindow(hwnd)
    IS_WIN.key_up(G.VK_TABLE["alt"])
    time.sleep(0.8)
    return user32.GetForegroundWindow() == hwnd


nh = find_notepad()
if nh:
    ok = force_foreground(nh)
    print("记事本窗口 hwnd=%d，抢前台%s" % (nh, "成功" if ok else "失败"))
else:
    print("没找到记事本窗口；下面这次 Win+H 会用当前前台窗口做实验")


def fg():
    h = user32.GetForegroundWindow()
    t = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, t, 512)
    c = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, c, 256)
    return int(h), t.value, c.value, proc_of(h)


print("当前前台窗口: 标题=%r 类名=%r 进程=%s" % fg()[1:])

base2 = snap()
IS_WIN.combo_tap(G.load_config().get("voice_hotkey") or "win+h")
time.sleep(2.8)
after2 = snap()
new = set(after2) - set(base2)
print("Win+H 之后，新窗口 %d 个：" % len(new))
for h in new:
    print("   标题=%r 类名=%r 进程=%s" % (after2[h][0], after2[h][1], proc_of(h)))
print()
if new:
    print("PASS  语音输入面板出现了（%s）"
          % G.key_spec_display(G.load_config().get("voice_hotkey") or "win+h"))
else:
    print("注意  没有新窗口。Win 键本身是通的（第 1 步已证明），")
    print("      所以这里是系统层面的原因，按顺序排查：")
    print("        1. 手动按一下键盘的 Win+H，看有没有反应")
    print("           · 手动也没反应 -> 系统语音输入被关了：")
    print("             设置 → 隐私和安全性 → 语音 → 打开「在线语音识别」")
    print("           · 手动有反应 -> 告诉我，我再换一种检测方式")
    print("        2. 麦克风是否接上并被允许访问")

esc()
# 注意：不要 terminate 记事本——它可能是用户自己开着的窗口，
# 我们只是借它当「有输入焦点的文本框」用，用完按 Esc 收尾就走。
print("\n已按 Esc 清理现场（不关闭记事本，避免误关你自己的窗口）。")
