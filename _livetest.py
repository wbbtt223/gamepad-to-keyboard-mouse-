# -*- coding: utf-8 -*-
"""真机测试：读取真实手柄，跑映射引擎（用记录型模拟器，不会真的点鼠标）。
运行期间请按手柄上的按钮 / 推摇杆，脚本会打印识别到的按钮与触发的动作。"""
import sys, time
import gamepad_mapper as G

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0


class Rec(object):
    def __init__(self):
        self.events = []

    def _e(self, *a):
        self.events.append(a)

    click = lambda self, b="left": self.events.append(("click", b))
    double_click = lambda self, b="left", gap=0.04: self.events.append(("double", b))
    mouse_down = lambda self, b="left": self.events.append(("down", b))
    mouse_up = lambda self, b="left": self.events.append(("up", b))
    key_tap = lambda self, vk: self.events.append(("key", G.vk_to_key_name(vk)))
    key_down = lambda self, vk: self.events.append(("keydown", G.vk_to_key_name(vk)))
    key_up = lambda self, vk: self.events.append(("keyup", G.vk_to_key_name(vk)))
    move = lambda self, dx, dy: self.events.append(("move", round(dx), round(dy)))
    scroll = lambda self, n: self.events.append(("scroll", n))
    release_all = lambda self: None


pad = G.Gamepad()
if not pad.available:
    print("pygame 不可用:", pad.error)
    sys.exit(2)
print("设备列表:", pad.names)
if not pad.connected:
    print("没有检测到手柄，插上后重试。")
    sys.exit(1)
print("已连接: %s   按钮 %d / 摇杆 %d / 十字键 %d"
      % (pad.name, pad.nbuttons, pad.naxes, pad.nhats))
print("可映射的按钮索引:", pad.all_button_ids())
print("请在 %.0f 秒内按手柄按钮 / 推摇杆 ……" % DURATION)
print("-" * 58)

cfg = G.default_config()
cfg["hotkey"] = {"enabled": False}
cfg["mouse"]["stick"] = "none"          # 避免摇杆漂移刷屏
rec = Rec()
eng = G.Engine(cfg, rec)
eng.start()

seen = set()
prev = set()
t0 = time.time()
try:
    while time.time() - t0 < DURATION:
        pad.poll()
        cur = {i for i, v in pad.buttons.items() if v}
        for i in sorted(cur - prev):
            name = pad.button_name(i)
            m = eng.mapping_for(i)
            print("  [按下] %-14s -> %s / %s%s" % (
                name, G.ACTION_LABELS.get(m.get("action"), "?"),
                G.MODE_LABELS.get(m.get("mode"), "?"),
                (" 键=" + m["key"]) if m.get("key") else ""))
            seen.add(i)
        for i in sorted(prev - cur):
            print("  [松开] %s" % pad.button_name(i))
        prev = cur

        if len(pad.axes) >= 4:
            for k in range(4):
                if abs(pad.axes[k]) > 0.5:
                    print("  [摇杆] 轴%d = %+.2f" % (k, pad.axes[k]))
                    seen.add(G.DPAD_BASE + 90 + k)
        for h in range(pad.nhats):
            if pad.hats[h] != (0, 0):
                print("  [十字键] %s" % (pad.hats[h],))
                seen.add(G.DPAD_BASE + 80 + h)

        eng.update(pad.buttons, pad.axes, pad.hats)
        time.sleep(0.004)
except KeyboardInterrupt:
    pass
finally:
    eng.stop()

print("-" * 58)
print("识别到的手柄输入索引:", sorted(seen) if seen else "无（测试期间没有按任何按钮）")
counts = {}
for e in rec.events:
    counts[e[0]] = counts.get(e[0], 0) + 1
print("引擎触发的动作统计:", counts if counts else "无")
moves = [e for e in rec.events if e[0] == "move"]
if moves:
    print("鼠标移动累计 dx=%d dy=%d"
          % (sum(m[1] for m in moves), sum(m[2] for m in moves)))
print("OK: 真机链路 %s" % ("已确认可用" if rec.events or seen else "手柄可读，但未观察到输入"))
