# -*- coding: utf-8 -*-
"""真机验证：右摇杆 -> 滚轮。

只把动作记录到内存，**不真的发滚轮事件**，所以不会滚动你眼前的窗口。
用法：python _livetest_scroll.py [秒数]
"""
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import gamepad_mapper as G


class Rec(object):
    """记录型模拟器：只记账，不注入。"""

    def __init__(self):
        self.events = []
        self.enabled = True

    def scroll(self, n):
        self.events.append(("scroll", n, time.perf_counter()))

    def move(self, dx, dy):
        pass

    def click(self, b="left"):
        pass

    def double_click(self, b="left", gap=0.04):
        pass

    def mouse_down(self, b="left"):
        pass

    def mouse_up(self, b="left"):
        pass

    def key_down(self, vk):
        pass

    def key_up(self, vk):
        pass

    def key_tap(self, vk):
        pass

    def release_all(self):
        pass


DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 16.0
AXIS = 3

print("=" * 64)
print("右摇杆滚轮 · 真机验证（只记录，不会滚动你的屏幕）")
print("请在接下来的 %.0f 秒里依次做两件事：" % DUR)
print("  1) 把【右摇杆向上】推到底，保持大约 2 秒，然后松手")
print("  2) 把【右摇杆向下】推到底，保持大约 2 秒，然后松手")
print("=" * 64)

pad = G.Gamepad()
if not pad.available:
    print("pygame 不可用:", pad.error)
    sys.exit(2)
pad.rescan()
if not pad.connected:
    print("未检测到手柄:", pad.error)
    sys.exit(2)
print("手柄: %s   轴 %d / 按钮 %d / 十字键 %d"
      % (pad.name, pad.naxes, pad.nbuttons, pad.nhats))

cfg = G.default_config()
cfg["hotkey"] = {"enabled": False}
cfg["mouse"]["stick"] = "none"          # 排除鼠标摇杆干扰
cfg["mouse"]["right_stick_scroll"] = True
sim = Rec()
eng = G.Engine(cfg, sim)
eng.start()

THRESH = 0.55
pushes = []
cur = None
t0 = time.perf_counter()
last_rate_print = t0


def close(c, now):
    evs = sim.events[c["n0"]:]
    return {"peak": c["peak"], "sign": c["sign"], "dur": now - c["t0"],
            "steps": sum(n for _, n, _ in evs), "n": len(evs)}


while time.perf_counter() - t0 < DUR:
    pad.poll()
    eng.update(pad.buttons, pad.axes, pad.hats)
    try:
        v = float(pad.axes[AXIS]) if len(pad.axes) > AXIS else 0.0
    except (TypeError, ValueError):
        v = 0.0
    now = time.perf_counter()
    # 每 3 秒报一次进度，方便确认脚本还活着
    if now - last_rate_print > 3.0:
        last_rate_print = now
        print("   ... 剩余 %.0fs   轴3=%+.2f   实时速率 %+.2f 格/秒"
              % (DUR - (now - t0), v, eng.scroll_rate))
    if abs(v) > THRESH:
        sgn = -1 if v < 0 else 1
        if cur is None:
            cur = {"sign": sgn, "peak": v, "t0": now, "n0": len(sim.events)}
        elif cur["sign"] != sgn:
            pushes.append(close(cur, now))
            cur = {"sign": sgn, "peak": v, "t0": now, "n0": len(sim.events)}
        elif abs(v) > abs(cur["peak"]):
            cur["peak"] = v
    elif cur is not None:
        pushes.append(close(cur, now))
        cur = None
    time.sleep(0.008)

if cur is not None:
    pushes.append(close(cur, time.perf_counter()))

print("-" * 64)
if not pushes:
    print("没有抓到推动样本。再跑一次，把摇杆推到底并多保持一会儿。")
    sys.exit(1)

for i, p in enumerate(pushes, 1):
    print("  推动 #%d  轴3=%+.2f  持续 %.2fs  ->  发出 %+d 格（%d 次滚轮事件）  %s"
          % (i, p["peak"], p["dur"], p["steps"], p["n"],
             "向上滚" if p["steps"] > 0 else ("向下滚" if p["steps"] < 0 else "无输出")))

up = [p for p in pushes if p["peak"] < 0 and p["dur"] > 0.4]
dn = [p for p in pushes if p["peak"] > 0 and p["dur"] > 0.4]
print("-" * 64)
if up and dn:
    a = sum(p["steps"] for p in up)
    b = sum(p["steps"] for p in dn)
    print("上推（轴3 为负）合计 %+d 格   下推（轴3 为正）合计 %+d 格" % (a, b))
    if a > 0 and b < 0:
        print("方向自检: 通过 —— 推上 = 向上滚，推下 = 向下滚（默认映射正确）")
    else:
        print("方向自检: 不一致 —— 在面板上勾「反向（向上推 = 向下滚）」")
else:
    print("样本不足：需要「向上推」和「向下推」各一次、每次保持 0.4 秒以上。")
    print("已抓到的样本：", [(p["peak"], p["dur"]) for p in pushes])
