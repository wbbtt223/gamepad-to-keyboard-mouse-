# -*- coding: utf-8 -*-
"""十字键「快进 / 快退」验证。

两种模式：
  python _livetest_ff.py --probe     硬验证：注入 → 低层键盘钩子拦截 →
                                     看系统到底把它识别成方向键还是小键盘 4/6
                                     （钩子返回 1 会吞掉事件，桌面不受影响）
  python _livetest_ff.py 20          真机监听：读真实手柄，按十字键左右，
                                     打印引擎实际发出的方向键与次数

为什么需要 --probe：方向键（VK_LEFT/VK_RIGHT）和小键盘 4/6 的扫描码前缀
是同一个字节，只靠「扩展标志」区分。少了标志，播放器收到的是数字 4/6，
快进就变成在进度条上打数字 —— 这类错误程序内部完全看不出来，
必须从系统层面观测注入事件的真实 vkCode。
"""
import ctypes
import sys
import time
import threading
from ctypes import wintypes

import gamepad_mapper as G

# ---------------------------------------------------------------- Win32
WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
PM_REMOVE = 0x0001
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10

VK_NAMES = {0x25: "← 左方向键", 0x27: "→ 右方向键",
            0x64: "小键盘 4", 0x66: "小键盘 6",
            0x26: "↑ 上方向键", 0x28: "↓ 下方向键",
            0x5B: "左 Win", 0x48: "H", 0x52: "R"}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt", POINT),
                ("lPrivate", wintypes.DWORD)]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_void_p, wintypes.DWORD]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                              wintypes.WPARAM, wintypes.LPARAM)


# ---------------------------------------------------------------- probe
def probe():
    print("=" * 66)
    print("硬验证：注入方向键，从系统层面看它被识别成什么")
    print("（钩子会吞掉这些按键，你屏幕上不会有任何反应）")
    print("=" * 66)

    seen = []
    block = [True]                      # True = 吞掉事件

    def on_key(ncode, wparam, lparam):
        if ncode == 0:
            kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            seen.append((wparam, kb.vkCode, kb.scanCode, kb.flags))
            if block[0]:
                return 1                # 非零 = 事件到此为止，不下发
        return user32.CallNextHookEx(None, ncode, wparam, lparam)

    proc = HOOKPROC(on_key)             # 必须留引用，否则被 GC
    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, None, 0)
    if not hook:
        print("装钩子失败，错误码 %d" % ctypes.get_last_error())
        return False

    sim = G.InputSimulator()

    def inject():
        time.sleep(0.7)
        for key, tag in (("right", "生产路径 →（快进键）"),
                         ("left", "生产路径 ←（快退键）"),
                         ("numpad4", "对照：小键盘 4"),
                         ("esc", "生产路径 ESC（LB 键）")):
            print("  注入 %s" % tag)
            sim.key_down(G.key_to_vk(key))
            time.sleep(0.06)
            sim.key_up(G.key_to_vk(key))
            time.sleep(0.15)

    t = threading.Thread(target=inject)
    t.daemon = True
    t.start()

    deadline = time.time() + 3.2
    msg = MSG()
    while time.time() < deadline:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.008)
    user32.UnhookWindowsHookEx(hook)

    print()
    print("捕获到的注入事件（全部已阻断）:")
    kd = [e for e in seen if e[0] in (WM_KEYDOWN, WM_SYSKEYDOWN)]
    for wparam, vk, scan, flags in kd:
        print("   vkCode=0x%02X (%-12s) scan=0x%02X  扩展=%s  注入=%s"
              % (vk, VK_NAMES.get(vk, "?"), scan,
                 "是" if flags & LLKHF_EXTENDED else "否",
                 "是" if flags & LLKHF_INJECTED else "否"))

    # 前两次是生产路径（→ / ←），第三次是故意的对照组（小键盘 4），第四次是 LB 的 ESC
    prod, ctrl, esc = kd[:2], kd[2:3], kd[3:4]

    print()
    ok = True
    if [e[1] for e in prod] == [0x27, 0x25]:
        print("✓ 生产路径注入的是 0x27(→) / 0x25(←) —— 正是快进/快退要的键")
    else:
        ok = False
        print("✗ 生产路径注入的键不对: %s" % [hex(e[1]) for e in prod])

    if prod and all(e[3] & LLKHF_EXTENDED for e in prod):
        print("✓ 两个方向键都带扩展标志 —— 不会被系统当成小键盘")
    else:
        ok = False
        print("✗ 缺扩展标志，播放器会收到小键盘数字而不是方向键")

    if ctrl and ctrl[0][1] == 0x64 and not (ctrl[0][3] & LLKHF_EXTENDED):
        print("✓ 对照组（不带扩展标志的 scan=0x4B）果然被识别成小键盘 4")
        print("  —— 这条对照证明「扩展标志」就是方向键与小键盘的唯一分水岭，")
        print("     也证明钩子确实读到了真实 vkCode，不是自己编的。")
    else:
        print("· 对照组: %s" % ([hex(e[1]) for e in ctrl] or "未捕获"))

    if esc and esc[0][1] == 0x1B:
        print("✓ LB 的 ESC 注入正确：vkCode=0x1B / scan=0x%02X / 不需要扩展标志"
              % esc[0][2])
    else:
        ok = False
        print("✗ LB 的 ESC 注入不对: %s" % ([hex(e[1]) for e in esc] or "未捕获"))

    print()
    if ok:
        print("结论：快进/快退注入正确。%d 个事件全部被钩子吞掉，桌面无干扰。" % len(seen))
    return ok


# ---------------------------------------------------------------- live
class Rec(object):
    def __init__(self):
        self.events = []

    key_tap = lambda self, vk: self.events.append(("key", G.vk_to_key_name(vk)))
    key_down = lambda self, vk: self.events.append(("keydown", G.vk_to_key_name(vk)))
    key_up = lambda self, vk: self.events.append(("keyup", G.vk_to_key_name(vk)))
    click = lambda self, b="left": self.events.append(("click", b))
    double_click = lambda self, b="left", gap=0.04: self.events.append(("double", b))
    mouse_down = lambda self, b="left": self.events.append(("down", b))
    mouse_up = lambda self, b="left": self.events.append(("up", b))
    move = lambda self, dx, dy: None
    scroll = lambda self, n: self.events.append(("scroll", n))
    release_all = lambda self: None


def live(duration):
    cfg = G.load_config()                 # 用你实际生效的配置
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "none"

    pad = G.Gamepad()
    if not pad.available:
        print("pygame 不可用:", pad.error)
        return False
    if not pad.connected:
        print("没有检测到手柄，插上后重试。")
        return False
    print("已连接: %s" % pad.name)
    for idx, label in ((101, "十字键 右 = → 快进"),
                       (103, "十字键 左 = ← 快退")):
        m = G.Engine(cfg, Rec()).mapping_for(idx)
        print("   [%d] %s  ->  key=%s / %s / hz=%s"
              % (idx, label, m.get("key"), m.get("mode"), m.get("hz")))
    print()
    print("请在 %.0f 秒内：推十字键【右】按住 1 秒 → 松手 → 推【左】按住 1 秒 → 松手"
          % duration)
    print("-" * 66)

    rec = Rec()
    eng = G.Engine(cfg, rec)
    eng.start()

    pressed = {}
    prev = set()
    seen_any = set()
    hat_seen = []
    last_hats = None
    hit = set()
    done_at = None
    t0 = time.time()
    while time.time() - t0 < duration:
        pad.poll()
        cur = {i for i, v in pad.buttons.items() if v}
        seen_any |= cur

        # 十字键原始读数（诊断用：万一手柄把十字键当按钮而非 hat）
        now_hats = list(pad.hats)
        if now_hats != last_hats:
            last_hats = now_hats
            if any(h != (0, 0) for h in now_hats):
                hat_seen.append(now_hats)
                print("  [十字键原始值] %s" % now_hats)

        for i in sorted(cur - prev):
            pressed[i] = len(rec.events)
            print("  [按下] %-12s (idx %d)" % (pad.button_name(i), i))
        for i in sorted(prev - cur):
            base = pressed.pop(i, None)
            if base is None:
                continue
            fired = rec.events[base:]
            got = [e[1] for e in fired if e[0] == "key"]
            if i in (101, 103) and got:
                hit.add(i)
                done_at = done_at or time.time()
            print("  [松开] %-12s -> 发出 %d 次 %s"
                  % (pad.button_name(i), len(got),
                     ",".join(sorted(set(got))) or "无"))
        eng.update({i: (i in cur) for i in cur})
        prev = cur
        # 左右都验证到就提前收工，不用干等
        if len(hit) >= 2 and time.time() - done_at > 1.0:
            print("  （左右都已验证，提前结束）")
            break
        time.sleep(0.008)

    print("-" * 66)
    allkeys = [e[1] for e in rec.events if e[0] == "key"]
    from collections import Counter
    cnt = Counter(allkeys)
    print("本次共发出方向键:", dict(cnt) if cnt else "无")
    if seen_any:
        print("期间读到的按钮索引:", sorted(seen_any),
              "->", [pad.button_name(i) for i in sorted(seen_any)])
    else:
        print("期间一个按钮都没读到。")
    print("期间读到的十字键(hat)原始值:", hat_seen if hat_seen else "无")
    ok = cnt.get("right", 0) > 0 and cnt.get("left", 0) > 0
    if ok:
        print("结论（真机）：十字键右 -> right(快进) %d 次，左 -> left(快退) %d 次"
              % (cnt.get("right", 0), cnt.get("left", 0)))
    else:
        print("结论（真机）：没读到两个方向都触发。若你确实按了，把现象告诉我。")
    return ok


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--probe" in sys.argv:
        sys.exit(0 if probe() else 1)
    d = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    sys.exit(0 if live(d) else 1)
