# -*- coding: utf-8 -*-
"""验证「假连接」判定与守护策略（纯逻辑，不碰真实手柄）。"""
import time
import gamepad_mapper as G

FAIL = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + ("  " + extra if extra else ""))
    if not cond:
        FAIL.append(name)


class FakeXI(object):
    """可编程的 XInput 探针替身。"""
    available = True

    def __init__(self, slot, buttons=0, usable=True):
        self.slot = slot
        self.buttons = buttons
        self.usable = usable

    def read(self):
        if not self.usable:
            return None, None            # 探针不可用
        if self.slot is None:
            return None, {}              # 明确「一个都没连」
        return self.slot, {"packet": 1, "buttons": self.buttons}


def mkpad(name, xi, sdl_buttons=None, seen=False):
    g = G.Gamepad.__new__(G.Gamepad)
    g.js = object()                      # 假装握着句柄
    g.name = name
    g.xinput = xi
    g.stale = False
    g._stale_since = 0.0
    g._xinput_seen = seen
    g.last_error = ""
    return g


print("== 1. XInput 说「没连」，SDL 却说连着 → 假连接 ==")
g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(None), seen=True)
g._check_stale({})
check("第一次只记时间，不立刻下结论", g.stale is False)
g._stale_since = time.time() - 1.0       # 模拟异常已持续 1 秒
g._check_stale({})
check("持续超过 0.6s 后判定为假连接", g.stale is True, g.last_error)

print("== 2. 以前从没连过（可能不被 XInput 支持）→ 不判假连接 ==")
g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(None), seen=False)
g._stale_since = time.time() - 5.0
g._check_stale({})
check("没有'曾经连过'的证据就不下结论", g.stale is False)

print("== 3. XInput 有按键、SDL 死寂 → 假连接 ==")
g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(0, buttons=0x1000))
g._check_stale({})
check("单帧不判定", g.stale is False)
g._stale_since = time.time() - 1.0
g._check_stale({})
check("持续后判定为假连接", g.stale is True)

print("== 4. XInput 与 SDL 都有按键 → 正常，不算假连接 ==")
g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(0, buttons=0x1000))
g._check_stale({0: True})
check("两条路径都收到按键 → 不报警", g.stale is False)

print("== 5. 手柄静止（XInput 无按键）但轴在乱跳 → 绝不能误报 ==")
for i in range(40):
    g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(0, buttons=0))
    g._stale_since = time.time() - 3.0
    g._check_stale({})                   # 静止、无输入
    if g.stale:
        break
check("静止时永远不会被误判为假连接（轴漂移免疫）", g.stale is False)

print("== 6. 非 Xbox 类手柄 → 不参与 XInput 判定 ==")
g = mkpad("Generic USB Joystick", FakeXI(None), seen=True)
g._stale_since = time.time() - 5.0
g._check_stale({})
check("杂牌手柄不误伤", g.stale is False)

print("== 7. 探针不可用（非 Windows / 无 xinput DLL）→ 不下结论 ==")
g = mkpad("Controller (XBOX 360 For Windows)", FakeXI(None, usable=False), seen=True)
g._stale_since = time.time() - 5.0
g._check_stale({})
check("探针不可用时保持沉默", g.stale is False)


class FakePad(object):
    available = True

    def __init__(self, connected=True, stale=False):
        self.connected = connected
        self.stale = stale
        self.calls = []

    def rescan(self):
        self.calls.append("rescan")
        self.stale = False               # 真实 rescan 会清掉 stale
        return 1

    def deep_reset(self):
        self.calls.append("deep_reset")
        self.stale = False
        return 1


print("== 8. 守护策略：假连接时先重扫、再动大手术 ==")
pad = FakePad(connected=True, stale=True)
st = {}
G.supervise_pad(pad, st)
check("第一次尝试用轻量 rescan", pad.calls[:1] == ["rescan"], str(pad.calls))
pad.stale = True
st["next_recover"] = 0.0
G.supervise_pad(pad, st)
check("第二次升级为 deep_reset", pad.calls[:2] == ["rescan", "deep_reset"], str(pad.calls))
pad.stale = True
st["next_recover"] = time.time() + 5.0
n = len(pad.calls)
G.supervise_pad(pad, st)
check("退避期内不再动手", len(pad.calls) == n)

print("== 9. 守护策略：真正未连接时每 2 秒扫一次 ==")
pad = FakePad(connected=False, stale=False)
st = {}
G.supervise_pad(pad, st)
check("立刻扫一次", pad.calls == ["rescan"], str(pad.calls))
st["last_scan"] = time.time()
G.supervise_pad(pad, st)
check("2 秒内不重复扫", pad.calls == ["rescan"])

print("== 10. 守护策略：正常连接、长时间空闲 → 心跳重枚举 ==")
pad = FakePad(connected=True, stale=False)
st = {"last_input": time.time() - 30, "last_idle": time.time() - 30}
G.supervise_pad(pad, st)
check("空闲够久就重枚举一次", pad.calls == ["rescan"], str(pad.calls))
st["last_idle"] = time.time()
G.supervise_pad(pad, st)
check("不会每帧都重枚举", pad.calls == ["rescan"])

print("== 11. 有输入时不打扰 ==")
pad = FakePad(connected=True, stale=False)
st = {"last_input": time.time(), "last_idle": 0.0}
G.supervise_pad(pad, st)
check("正在使用手柄时不动它", pad.calls == [], str(pad.calls))

print("== 12. pad_input_seen 的判定 ==")
class P(object):
    buttons = {0: False}; axes = [0.0, 0.0]
check("全静止 = 无输入", G.pad_input_seen(P()) is False)
P.buttons = {0: True}
check("有按键 = 有输入", G.pad_input_seen(P()) is True)
P.buttons = {0: False}; P.axes = [0.0, 0.9]
check("摇杆推动 = 有输入", G.pad_input_seen(P()) is True)

print()
print("失败项:", FAIL if FAIL else "无")
raise SystemExit(1 if FAIL else 0)
