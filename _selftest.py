# -*- coding: utf-8 -*-
"""离线自测：用记录型模拟器替换 SendInput，验证映射引擎逻辑。"""
import sys, time
import gamepad_mapper as G


class Rec(object):
    def __init__(self):
        self.events = []
        self.enabled = True

    def click(self, b="left"):
        self.events.append(("click", b))

    def double_click(self, b="left", gap=0.04):
        self.events.append(("dbl", b))

    def mouse_down(self, b="left"):
        self.events.append(("down", b))

    def mouse_up(self, b="left"):
        self.events.append(("up", b))

    def key_tap(self, vk):
        self.events.append(("keytap", vk))

    def combo_tap(self, spec):
        """照着 InputSimulator.combo_tap 的顺序记录，方便断言顺序。"""
        mods, vk = G.parse_key_spec(spec)
        for m in mods:
            self.events.append(("keydown", m))
        self.events.append(("keytap", vk))
        for m in reversed(mods):
            self.events.append(("keyup", m))

    def key_down(self, vk):
        self.events.append(("keydown", vk))

    def key_up(self, vk):
        self.events.append(("keyup", vk))

    def move(self, dx, dy):
        self.events.append(("move", round(dx), round(dy)))

    def scroll(self, n):
        self.events.append(("scroll", n))

    def release_all(self):
        self.events.append(("release_all",))

    def of(self, kind):
        return [e for e in self.events if e[0] == kind]


def mk(buttons):
    cfg = G.default_config()
    cfg["buttons"] = buttons
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "none"
    cfg["mouse"]["right"]["mouse"] = False       # 隔离：只验按键
    return cfg


def test_tap_click():
    cfg = mk({"0": {"action": "mouse_left", "mode": "tap", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({0: True}); e.update({0: True}); e.update({0: False})
    assert len(r.of("click")) == 1, r.events
    print("PASS tap-click")

def test_no_repeat_on_hold():
    cfg = mk({"0": {"action": "mouse_left", "mode": "tap", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(10):
        e.update({0: True}); time.sleep(0.004)
    assert len(r.of("click")) == 1, r.events
    print("PASS hold-does-not-repeat")

def test_double_click():
    cfg = mk({"2": {"action": "mouse_double", "mode": "tap", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({2: True}); e.update({2: False})
    assert len(r.of("dbl")) == 1, r.events
    print("PASS double-click")

def test_rapid():
    cfg = mk({"0": {"action": "mouse_left", "mode": "rapid", "hz": 50, "key": ""}})
    # 本测试只验「频率」：关掉启动延迟，否则前 0.4s 属于延迟期（只触发 1 次）
    cfg["rapid_delay"] = 0.0
    r = Rec(); e = G.Engine(cfg, r); e.start()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.5:
        e.update({0: True})
        time.sleep(0.004)
    e.update({0: False})
    n = len(r.of("click"))
    assert 12 <= n <= 32, "50Hz*0.5s 期望约25次, 实际 %d" % n
    print("PASS rapid-click  0.5s -> %d 次 (50Hz)" % n)

def test_hold_mouse():
    cfg = mk({"0": {"action": "mouse_left", "mode": "hold", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(5):
        e.update({0: True}); time.sleep(0.003)
    e.update({0: False})
    assert len(r.of("down")) == 1 and len(r.of("up")) == 1, r.events
    print("PASS hold-mouse (按下保持/松开释放)")

def test_a_button_default_is_hold():
    """A(0) 默认必须是「按住不放」：快点一下=单击，长按=左键保持按下。
    若被改回 tap，长按会完全失效（用户报过「A 键没办法长按」）。"""
    d = G.default_config()
    assert d["buttons"]["0"]["action"] == "mouse_left", d["buttons"]["0"]
    assert d["buttons"]["0"]["mode"] == "hold", d["buttons"]["0"]
    c = G.load_config()
    assert c["buttons"]["0"]["action"] == "mouse_left", c["buttons"]["0"]
    assert c["buttons"]["0"]["mode"] == "hold", c["buttons"]["0"]
    print("PASS A(0) 默认 = 鼠标左键 + 按住不放（tap 会让长按失效）")

def test_a_hold_long_press_holds_left_button():
    """行为验证：A 长按期间左键保持按下（只按下 1 次），松手才释放。"""
    cfg = mk({"0": {"action": "mouse_left", "mode": "hold", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({0: True})
    for _ in range(10):
        e.update({0: True}); time.sleep(0.005)
    e.update({0: False})
    assert r.of("down") == [("down", "left")], r.events
    assert r.of("up") == [("up", "left")], r.events
    print("PASS A 长按 = 左键保持按下，松手释放")

def test_key_rapid():
    cfg = mk({"11": {"action": "key", "mode": "rapid", "hz": 40, "key": "space"}})
    cfg["rapid_delay"] = 0.0     # 同上：只验频率
    r = Rec(); e = G.Engine(cfg, r); e.start()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.4:
        e.update({11: True})
        time.sleep(0.004)
    e.update({11: False})
    n = len(r.of("keytap"))
    assert 10 <= n <= 26, n
    assert all(x[1] == 0x20 for x in r.of("keytap"))
    print("PASS rapid-key 'space'  0.4s -> %d 次 (40Hz)" % n)

def test_rapid_hold_delay():
    """连发「启动延迟」：点一下只触发 1 次，按住超过延迟才连续触发。

    真实故障：Y=退格 用 rapid，点一下却删了 3 个字母（按下即连发，几十毫秒就补发 2~3 次）。
    修法：按下后先等 rapid_delay，延迟内松手只发第一次。
    """
    cfg = mk({"3": {"action": "key", "mode": "rapid", "hz": 20, "key": "backspace"}})
    d = G.default_config()
    assert d.get("rapid_delay") == 0.4, d.get("rapid_delay")   # 默认必须有延迟

    r = Rec(); e = G.Engine(cfg, r); e.start()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.10:                     # 快按 0.1s << 0.4s
        e.update({3: True}); time.sleep(0.004)
    e.update({3: False})
    tap = len(r.of("keytap"))
    assert tap == 1, "点一下应只触发 1 次，实际 %d" % tap

    r2 = Rec(); e2 = G.Engine(cfg, r2); e2.start()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 1.00:                     # 按住 1.0s
        e2.update({3: True}); time.sleep(0.004)
    e2.update({3: False})
    hold = len(r2.of("keytap"))
    assert hold >= 8, "按住 1s 应连续触发多次，实际 %d" % hold

    # 延迟设 0 = 旧行为：0.1s 也会补发多次
    cfg0 = dict(cfg); cfg0["rapid_delay"] = 0.0
    r3 = Rec(); e3 = G.Engine(cfg0, r3); e3.start()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.10:
        e3.update({3: True}); time.sleep(0.004)
    e3.update({3: False})
    old = len(r3.of("keytap"))
    assert old > 1, "delay=0 时应恢复「按下即连发」，实际 %d" % old
    print("PASS rapid 启动延迟：点一下 %d 次 / 按住 1s %d 次 / delay=0 点一下 %d 次"
          % (tap, hold, old))

def test_toggle():
    cfg = mk({"6": {"action": "toggle", "mode": "tap", "hz": 20, "key": ""},
              "0": {"action": "mouse_left", "mode": "tap", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({6: True}); e.update({6: False})
    assert e.enabled is False
    e.update({0: True}); e.update({0: False})      # 关闭后不应触发
    assert len(r.of("click")) == 0, r.events
    e.update({6: True}); e.update({6: False})
    assert e.enabled is True
    e.update({0: True}); e.update({0: False})
    assert len(r.of("click")) == 1, r.events
    print("PASS toggle 开关映射")

def test_dpad_virtual():
    cfg = mk({"100": {"action": "wheel_up", "mode": "tap", "hz": 20, "key": ""}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({100: True}); e.update({100: False})
    assert r.of("scroll") == [("scroll", 1)], r.events
    print("PASS 十字键虚拟按钮 -> 滚轮")

def test_stick_move():
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "left"
    cfg["mouse"]["sensitivity"] = 1000
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(10):
        e.update({}, [0.9, 0.0, 0.0, 0.0, 0.0, 0.0])
        time.sleep(0.01)
    moves = r.of("move")
    assert moves and sum(m[1] for m in moves) > 0, moves
    print("PASS 摇杆推鼠标 (累计 dx=%d)" % sum(m[1] for m in moves))


# ===========================================================================
# 右摇杆 = 低灵敏度移动鼠标（精调）
# ===========================================================================

def _move_total(axes, **over):
    """推某个方向 10 帧，返回鼠标累计位移（左/右都由 axes 决定）。"""
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "left"
    for k, v in over.items():
        cfg["mouse"][k] = v
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(10):
        e.update({}, axes)
        time.sleep(0.01)
    return sum(m[1] for m in r.of("move")), r


def test_right_stick_slow_mouse():
    """右摇杆要能搬鼠标，而且必须**明显比左摇杆慢**（更精准）。"""
    left, _ = _move_total([0.9, 0.0, 0.0, 0.0])
    right, r2 = _move_total([0.0, 0.0, 0.9, 0.0])
    assert left > 0, "左摇杆应搬动鼠标"
    assert right > 0, "右摇杆应搬动鼠标: %r" % r2.events
    assert right < left * 0.6, "右摇杆应明显更慢: left=%d right=%d" % (left, right)
    print("PASS 右摇杆低灵敏度鼠标（左=%d / 右=%d 像素）" % (left, right))


def test_right_stick_mouse_default_on():
    """出厂默认：右摇杆搬鼠标(低灵敏度)、右摇杆滚轮关闭。"""
    d = G.default_config()
    assert d["mouse"]["right"]["mouse"] is True, d["mouse"]["right"]
    assert d["mouse"]["right_stick_scroll"] is False, d["mouse"]
    assert d["mouse"]["right"]["sensitivity"] < d["mouse"]["sensitivity"], d["mouse"]
    print("PASS 默认 右摇杆=低灵敏度鼠标 / 右摇杆滚轮=关")


def test_right_stick_mouse_off_when_stick_none():
    """把「使用摇杆」设成不启用时，左右摇杆都不该再搬鼠标。"""
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "none"
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(10):
        e.update({}, [0.9, 0.0, 0.9, 0.0])
        time.sleep(0.01)
    assert r.of("move") == [], "stick=none 时摇杆不应搬鼠标: %r" % r.events
    print("PASS stick=none 时左右摇杆都不搬鼠标")


def test_right_stick_and_scroll_conflict():
    """右摇杆滚轮关掉后，右摇杆上下不该再产生滚动。"""
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "none"
    cfg["mouse"]["right"]["mouse"] = False
    cfg["mouse"]["right_stick_scroll"] = False
    r = Rec(); e = G.Engine(cfg, r); e.start()
    _run(e, [0, 0, 0, -1.0], 0.3)
    assert r.of("scroll") == [], "滚轮关闭时不应滚动: %r" % r.events
    print("PASS 右摇杆滚轮关闭后不再滚动")


def test_dpad_wheel_frequency():
    """十字键上下 = 滚轮，频率调低到 6 次/秒。"""
    d = G.default_config()
    assert d["buttons"]["100"]["action"] == "wheel_up", d["buttons"]["100"]
    assert d["buttons"]["102"]["action"] == "wheel_down", d["buttons"]["102"]
    assert d["buttons"]["100"]["hz"] == 6, d["buttons"]["100"]
    assert d["buttons"]["102"]["hz"] == 6, d["buttons"]["102"]
    print("PASS 十字键↑↓ = 滚轮 6 次/秒")


def test_left_right_sensitivity_independent():
    """左右摇杆灵敏度必须各存各的：改左不影响右，改右不影响左。"""
    d = G.default_config()
    assert d["mouse"]["sensitivity"] != d["mouse"]["right"]["sensitivity"], d["mouse"]
    cfg = G.default_config()
    # 面板只发「左摇杆灵敏度」这一个字段
    G._deep_merge(cfg, {"mouse": {"sensitivity": 900.0}})
    assert cfg["mouse"]["sensitivity"] == 900.0
    assert cfg["mouse"]["right"]["sensitivity"] == 500.0, "改左不该动到右"
    # 反过来只发「右摇杆灵敏度」
    G._deep_merge(cfg, {"mouse": {"right": {"sensitivity": 250.0}}})
    assert cfg["mouse"]["right"]["sensitivity"] == 250.0
    assert cfg["mouse"]["sensitivity"] == 900.0, "改右不该动到左"
    print("PASS 左右摇杆灵敏度互相独立（左 900 / 右 250 各自生效）")


def test_left_right_move_independent():
    """实际推杆时左右各自用各自的灵敏度与死区。"""
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "left"
    cfg["mouse"]["sensitivity"] = 1400
    cfg["mouse"]["deadzone"] = 0.90          # 左摇杆死区调到极大
    cfg["mouse"]["right"]["mouse"] = True
    cfg["mouse"]["right"]["sensitivity"] = 500
    cfg["mouse"]["right"]["deadzone"] = 0.10  # 右摇杆小死区
    r = Rec(); e = G.Engine(cfg, r); e.start()
    for _ in range(8):
        e.update({}, [0.0, 0.0, 0.6, 0.0])     # 0.6 撑不过左死区(0.90)，但过得了右死区(0.10)
        time.sleep(0.01)
    assert r.of("move"), "右摇杆应能移动（用自己的死区，不受左死区影响）: %r" % r.events
    print("PASS 右摇杆实际用自己的灵敏度/死区移动")


# ===========================================================================
# 右摇杆当滚轮（缓慢滚动）
# ===========================================================================

def _scroll_engine(**over):
    cfg = G.default_config()
    cfg["hotkey"] = {"enabled": False}
    cfg["mouse"]["stick"] = "none"           # 单验滚轮，排除鼠标摇杆干扰
    cfg["mouse"]["right"]["mouse"] = False   # 右摇杆不搬鼠标，避免混入 move 事件
    cfg["mouse"]["right_stick_scroll"] = True
    cfg["mouse"]["scroll"].update(over)
    r = Rec(); e = G.Engine(cfg, r); e.start()
    return cfg, r, e


def _run(e, axes, seconds, step=0.01):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        e.update({}, axes)
        time.sleep(step)


def _steps(r):
    """带符号总格数（向上为正）。"""
    return sum(n for _, n in r.of("scroll"))


def _abs_steps(r):
    return sum(abs(n) for _, n in r.of("scroll"))


def test_scroll_direction():
    cfg, r, e = _scroll_engine()
    _run(e, [0, 0, 0, -1.0], 0.35)
    up = _steps(r)
    assert up > 0, "向上推(轴3=-1)应当是正 notches=向上滚: %r" % r.events
    cfg2, r2, e2 = _scroll_engine()
    _run(e2, [0, 0, 0, 1.0], 0.35)
    dn = _steps(r2)
    assert dn < 0, "向下推(轴3=+1)应当是负 notches=向下滚: %r" % r2.events
    print("PASS 滚轮方向  上推=%+d 格 / 下推=%+d 格" % (up, dn))


def test_scroll_invert():
    cfg, r, e = _scroll_engine(invert=True)
    _run(e, [0, 0, 0, -1.0], 0.35)
    assert _steps(r) < 0, "invert 后上推应向下滚: %r" % r.events
    print("PASS 滚轮反向开关")


def test_scroll_deadzone():
    cfg, r, e = _scroll_engine()
    _run(e, [0, 0, 0, -0.20], 0.6)
    assert r.of("scroll") == [], "死区内不应滚动: %r" % r.events
    print("PASS 滚轮死区（0.20 < 0.22 不滚）")


def test_scroll_speed_full():
    """满推 1 秒 ≈ speed 格，这是「缓慢」的基准。"""
    cfg, r, e = _scroll_engine(speed=6.0)
    _run(e, [0, 0, 0, -1.0], 1.0)
    n = _steps(r)
    assert 4 <= n <= 8, "满推 1s @6格/秒 期望 ~6 格, 实际 %d" % n
    print("PASS 满推速度  1s -> %d 格（设定 6 格/秒，缓慢）" % n)


def test_scroll_speed_light():
    """轻推必须明显更慢，但不至于完全不动。"""
    cfg, r, e = _scroll_engine(speed=6.0)
    _run(e, [0, 0, 0, -0.40], 1.0)
    n = _steps(r)
    assert 0 <= n <= 2, "轻推(0.40)1s 应 ≤2 格, 实际 %d" % n
    print("PASS 轻推速度  (0.40) 1s -> %d 格（满推 6 格）" % n)


def test_scroll_stops_on_release():
    cfg, r, e = _scroll_engine(speed=20.0)
    _run(e, [0, 0, 0, -1.0], 0.5)
    assert _abs_steps(r) > 0, r.events
    r.events = []
    _run(e, [0, 0, 0, 0.0], 0.5)
    rest = _abs_steps(r)
    assert rest <= 2, "松手后应立刻停, 残留 %d 格: %r" % (rest, r.events)
    print("PASS 松手立刻停（残留 %d 格）" % rest)


def test_scroll_stick_none_still_works():
    """回归：鼠标摇杆设为「不启用」时，滚轮曾经被一起关掉。"""
    cfg, r, e = _scroll_engine()
    cfg["mouse"]["stick"] = "none"
    _run(e, [0, 0, 0, -1.0], 0.4)
    assert r.of("scroll"), "鼠标摇杆关闭时滚轮仍须工作: %r" % r.events
    print("PASS stick=none 时滚轮仍工作（bug 回归）")


def test_scroll_disabled():
    cfg, r, e = _scroll_engine()
    cfg["mouse"]["right_stick_scroll"] = False
    _run(e, [0, 0, 0, -1.0], 0.4)
    assert r.of("scroll") == [], r.events
    print("PASS 关闭滚轮后不动作")


def test_scroll_paused():
    cfg, r, e = _scroll_engine()
    assert e.toggle_enabled(False) is False
    _run(e, [0, 0, 0, -1.0], 0.4)
    assert r.of("scroll") == [], r.events
    assert e._scroll_acc == 0.0 and e._scroll_smooth == 0.0, "暂停时应清空累积器"
    print("PASS 暂停映射时滚轮停止且清空累积")


def test_scroll_reverse_no_jump():
    """攒下不足一格的余量后反向，不应先往反方向跳一格。"""
    cfg, r, e = _scroll_engine(speed=6.0)
    _run(e, [0, 0, 0, -0.5], 0.3)
    r.events = []
    _run(e, [0, 0, 0, 1.0], 0.25)
    up = sum(n for _, n in r.of("scroll") if n > 0)
    assert up == 0, "反向时不该先向上滚: %r" % r.events
    print("PASS 反向无跳格")


def test_scroll_limit():
    """单帧限幅：掉帧后不能瞬间跳好几页。"""
    cfg, r, e = _scroll_engine(speed=60.0, limit=4)
    e._scroll_smooth = 60.0
    e._handle_scroll_axes([0, 0, 0, -1.0], 0.5)      # 累积本应为 +30 格
    got = [n for _, n in r.of("scroll")]
    assert got == [4], "单帧应限幅到 +4, 实际 %r" % got
    print("PASS 单帧限幅（累积 +30 被限到 +4）")


def test_scroll_custom_axis():
    """可以把滚轮绑到别的轴（比如左摇杆或扳机）。"""
    cfg, r, e = _scroll_engine(axis=1, deadzone=0.2)
    _run(e, [0, -1.0, 0, 0], 0.4)
    assert _steps(r) > 0, "轴 1 应能驱动滚轮: %r" % r.events
    print("PASS 自定义滚轮轴（axis=1）")


def test_scroll_rate_reported():
    """面板读的 scroll_rate 要能反映真实速率。"""
    cfg, r, e = _scroll_engine(speed=6.0)
    _run(e, [0, 0, 0, -1.0], 0.3)
    assert e.scroll_rate > 4.0, "满推时 scroll_rate 应接近 6, 实际 %.2f" % e.scroll_rate
    _run(e, [0, 0, 0, 0.0], 0.3)
    assert abs(e.scroll_rate) < 0.3, "松手后应回落到 0, 实际 %.2f" % e.scroll_rate
    print("PASS 实时速率上报（满推 %.2f -> 松手 %.2f 格/秒）"
          % (6.0, e.scroll_rate))


# ===========================================================================
# 组合键 / 语音输入
# ===========================================================================

def test_parse_key_spec():
    assert G.parse_key_spec("win+h") == ([0x5B], 0x48)
    assert G.parse_key_spec("ctrl+shift+k") == ([0xA2, 0xA0], 0x4B)
    assert G.parse_key_spec("ctrl+c") == ([0xA2], 0x43)
    assert G.parse_key_spec("cmd+r") == ([0x5B], 0x52)      # cmd 归一化到左 Win
    assert G.parse_key_spec("win+ctrl+s") == ([0x5B, 0xA2], 0x53)
    assert G.parse_key_spec("a") == ([], 0x41)
    assert G.parse_key_spec("") == ([], None)
    assert G.parse_key_spec("win+不存在的键") == ([0x5B], None)
    assert G.parse_key_spec("ctrl+ctrl+k") == ([0xA2], 0x4B)  # 去重
    print("PASS 组合键解析（win+h / ctrl+shift+k / 别名 / 非法）")


def test_combo_tap_order():
    """真实注入器的调用顺序：修饰键先下、主键抬起后才释放修饰键。"""
    sim = G.InputSimulator.__new__(G.InputSimulator)   # 不走 __init__，不发真实按键
    calls = []
    sim.key_down = lambda vk: calls.append(("down", vk))
    sim.key_up = lambda vk: calls.append(("up", vk))
    sim.key_tap = lambda vk: calls.append(("tap", vk))
    sim.combo_tap("ctrl+shift+k")
    assert calls == [("down", 0xA2), ("down", 0xA0), ("tap", 0x4B),
                     ("up", 0xA0), ("up", 0xA2)], calls
    calls[:] = []
    sim.combo_tap("win+h")
    assert calls == [("down", 0x5B), ("tap", 0x48), ("up", 0x5B)], calls
    calls[:] = []
    sim.combo_tap("win+不存在的键")                     # 非法主键 -> 什么都不发
    assert calls == [], calls
    print("PASS 组合键注入顺序（修饰键按下 -> 主键 -> 逆序释放）")


def test_key_spec_display():
    assert G.key_spec_display("win+h") == "Win+H"
    assert G.key_spec_display("ctrl+shift+k") == "Ctrl+Shift+K"
    assert G.key_spec_display("a") == "A"
    assert G.key_spec_display("f5") == "f5"
    assert G.key_spec_display("") == ""
    print("PASS 组合键显示名")


def _voice_engine(mode="tap", hotkey="win+h", buttons=None):
    cfg = mk(buttons or {"4": {"action": "voice", "mode": mode, "hz": 20, "key": ""}})
    cfg["voice_hotkey"] = hotkey
    r = Rec(); e = G.Engine(cfg, r); e.start()
    return cfg, r, e


def test_voice_tap():
    cfg, r, e = _voice_engine()
    e.update({4: True}); e.update({4: False})
    assert r.of("keytap") == [("keytap", 0x48)], r.events
    assert r.of("keydown") == [("keydown", 0x5B)], "应当按下 Win 再按 H"
    assert r.of("keyup") == [("keyup", 0x5B)], "应当释放 Win"
    print("PASS 语音输入 按一下 = Win+H")


def test_voice_min_interval():
    """误设成连发也不能把听写面板刷爆。"""
    cfg, r, e = _voice_engine(mode="rapid")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.5:
        e.update({4: True})
        time.sleep(0.01)
    e.update({4: False})
    n = len(r.of("keytap"))
    assert 1 <= n <= 3, "0.5s 内应受最小间隔限制只发 1~2 次, 实际 %d" % n
    print("PASS 语音输入最小间隔保护（连发 0.5s -> %d 次）" % n)


def test_voice_hold():
    cfg, r, e = _voice_engine(mode="hold")
    e.update({4: True})
    e.update({4: True})
    e.update({4: True})
    assert len(r.of("keytap")) == 1, "按住期间只发一次(开始): %r" % r.events
    time.sleep(0.4)
    e.update({4: False})
    assert len(r.of("keytap")) == 2, "松开应再发一次(结束): %r" % r.events
    print("PASS 语音输入 按住不放 = 按住说/松开停")


def test_voice_custom_hotkey():
    cfg, r, e = _voice_engine(hotkey="ctrl+alt+v")
    e.update({4: True}); e.update({4: False})
    assert ("keytap", 0x56) in r.events, r.events
    assert ("keydown", 0xA2) in r.events and ("keydown", 0xA4) in r.events, r.events
    print("PASS 语音输入自定义组合键（Ctrl+Alt+V）")


def test_voice_bad_hotkey_fallback():
    cfg, r, e = _voice_engine(hotkey="win+根本没这个键")
    e.update({4: True}); e.update({4: False})
    assert r.of("keytap") == [("keytap", 0x48)], "非法组合键应回退到 Win+H: %r" % r.events
    print("PASS 非法语音组合键回退到 Win+H")


def test_voice_paused():
    cfg, r, e = _voice_engine()
    e.toggle_enabled(False)
    e.update({4: True}); e.update({4: False})
    assert r.of("keytap") == [], "暂停映射时不应触发语音: %r" % r.events
    print("PASS 暂停映射时语音输入不触发")


def test_voice_default_binding():
    """出厂默认：LB(4) = 键盘 ESC；Start(7) = 语音输入；默认组合键 Win+H。

    历史坑：语音原来绑在 LB，用户把 LB 改成 Esc 之后语音就「没键可用」了。
    这条同时守住两条：LB 必须是 Esc、Start 必须是语音输入。
    """
    d = G.default_config()
    assert d["buttons"]["4"] == {"action": "key", "mode": "tap", "hz": 20, "key": "esc"}, d["buttons"]["4"]
    assert d["buttons"]["7"]["action"] == "voice", d["buttons"]["7"]
    assert d["voice_hotkey"] == "win+h"
    c = G.load_config()
    assert c["buttons"]["4"]["action"] == "key" and c["buttons"]["4"]["key"] == "esc", c["buttons"]["4"]
    assert c["buttons"]["7"]["action"] == "voice", c["buttons"]["7"]
    print("PASS 默认绑定 LB=键盘 ESC / Start=语音输入(Win+H)")


def test_voice_bound_to_start_sends_win_h():
    """端到端：config.json 里的 Start(7) 按一下 = Win+H。"""
    c = G.load_config()
    r = Rec(); e = G.Engine(mk({"7": c["buttons"]["7"]}), r); e.start()
    e.update({7: True}); e.update({7: False})
    assert r.of("keytap") == [("keytap", 0x48)], r.events
    assert r.of("keydown") == [("keydown", 0x5B)], r.events
    print("PASS Start 键 按一下 = Win+H 语音输入")


# ---------------- 十字键 = 快进 / 快退 ----------------

# 测试用的固定频率（6Hz），只为在很短的时间里数得清次数；
# 真正出厂的频率是 1.2Hz，见 test_fastforward_shipped_rate。
def _ff_engine(mode="rapid", hz=6):
    cfg = mk({
        "101": {"action": "key", "mode": mode, "hz": hz, "key": "right"},
        "103": {"action": "key", "mode": mode, "hz": hz, "key": "left"},
    })
    r = Rec(); e = G.Engine(cfg, r); e.start()
    return cfg, r, e


def test_fastforward_direction():
    """十字键 右 = →(快进)，左 = ←(快退)，且是方向键 VK 不是小键盘。"""
    cfg, r, e = _ff_engine()
    e.update({101: True}); e.update({101: False})
    assert r.of("keytap") == [("keytap", 0x27)], r.events
    r.events = []
    e.update({103: True}); e.update({103: False})
    assert r.of("keytap") == [("keytap", 0x25)], r.events
    # 0x25/0x27 是 VK_LEFT/VK_RIGHT；若误发成 0x64/0x66 就变成小键盘 4/6 了
    assert 0x25 not in (0x64, 0x66) and 0x27 not in (0x64, 0x66)
    print("PASS 十字键 右=→快进 / 左=←快退（方向键 VK 0x27/0x25）")


def test_fastforward_rapid():
    """按住不放要连续发方向键（播放器才会连续快进），松手立刻停。"""
    cfg, r, e = _ff_engine()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.6:
        e.update({101: True})
        time.sleep(0.01)
    n = len(r.of("keytap"))
    assert 2 <= n <= 8, "6Hz 按住 0.6s 应发 3~5 次, 实际 %d" % n
    e.update({101: False})
    settled = len(r.of("keytap"))
    time.sleep(0.3)
    e.update({101: False})                  # 再喂几帧，确认真的停了
    e.update({101: False})
    assert len(r.of("keytap")) == settled, "松手后不应继续快进: %r" % r.events
    print("PASS 按住连续快进（0.6s -> %d 次），松手即停" % n)


def test_fastforward_paused():
    """暂停映射时不能偷偷快进。"""
    cfg, r, e = _ff_engine()
    e.toggle_enabled(False)
    e.update({101: True}); e.update({103: True})
    assert r.of("keytap") == [], "暂停时不应发方向键: %r" % r.events
    print("PASS 暂停映射时快进键不触发")


def test_fastforward_default_binding():
    """出厂默认：十字键右(101)=→、左(103)=←，且是「按一下跳一次」(tap)。"""
    d = G.default_config()
    assert d["buttons"]["101"] == {"action": "key", "mode": "tap", "hz": 1.2, "key": "right"}, d["buttons"]["101"]
    assert d["buttons"]["103"] == {"action": "key", "mode": "tap", "hz": 1.2, "key": "left"}, d["buttons"]["103"]
    print("PASS 默认绑定 十字键右=→快进 / 左=←快退（按一下跳一次）")


def test_fastforward_config_file():
    """落盘的 config.json 里就得是快进键（防止只改了代码没改配置）。"""
    c = G.load_config()
    assert c["buttons"]["101"]["key"] == "right", c["buttons"]["101"]
    assert c["buttons"]["103"]["key"] == "left", c["buttons"]["103"]
    assert c["buttons"]["101"]["mode"] == "tap", c["buttons"]["101"]
    assert c["buttons"]["103"]["mode"] == "tap", c["buttons"]["103"]
    print("PASS config.json 落盘校验 101=→ / 103=←（tap 单次）")


def test_fastforward_tap_once():
    """核心诉求：按一下只跳一次。

    播放器每响应一次方向键前进约 5 秒。以前是 rapid 连发，按住 1 秒会发 6 次
    （≈ 前进 30 秒）；现在必须是 tap —— **按住不放也只能发一次**。
    """
    c = G.load_config()
    assert c["buttons"]["101"]["mode"] == "tap", c["buttons"]["101"]
    assert c["buttons"]["103"]["mode"] == "tap", c["buttons"]["103"]

    r = Rec(); e = G.Engine(mk({"101": c["buttons"]["101"],
                                "103": c["buttons"]["103"]}), r); e.start()

    # 1) 快按一下 -> 恰好 1 次
    e.update({101: True}); e.update({101: False})
    assert len(r.of("keytap")) == 1, r.events

    # 2) 按住整整 3 秒 -> 仍然只有 1 次（这是关键：不能再连发）
    r.events = []                           # 清掉第 1 步那次，单独数这一轮
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 3.0:
        e.update({101: True})
        time.sleep(0.01)
    e.update({101: False})
    n = len(r.of("keytap"))
    assert n == 1, "按住 3 秒应只发 1 次（≈前进 5 秒），实际 %d 次（≈前进 %d 秒）" % (n, n * 5)

    # 3) 快退同理
    r.events = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 1.5:
        e.update({103: True})
        time.sleep(0.01)
    e.update({103: False})
    assert len(r.of("keytap")) == 1, r.events

    # 4) 连按三下 -> 3 次（每次按一下跳一次，不累积、不丢）
    r.events = []
    for _ in range(3):
        e.update({101: True}); e.update({101: False})
    assert len(r.of("keytap")) == 3, r.events

    print("PASS 按一下只跳一次：快按 1 次 / 按住 3 秒仍 1 次 / 连按 3 下 = 3 次")


def _mock_pad_with_hat():
    """造一个只有十字键(hat)的手柄，用来验证 hat -> 虚拟索引这条链路。"""
    pad = G.Gamepad.__new__(G.Gamepad)      # 不走 __init__，不碰真实设备
    pad.available, pad.pygame, pad._pump_ok = True, None, False
    pad.nbuttons, pad.naxes, pad.nhats = 0, 0, 1
    pad.buttons, pad.axes, pad.hats = {}, [], []
    pad.error = pad.last_error = ""
    pad.rescan = lambda: None
    holder = {"hat": (0, 0)}

    class JS(object):
        def get_hat(self, i):
            return holder["hat"]

    pad.js = JS()
    return pad, holder


def test_dpad_hat_to_index():
    """十字键是 hat，不是 button —— poll() 要把它翻译成 101/103。

    这条是「快进键」的前半段：真实手柄读数 -> 虚拟索引。
    """
    pad, holder = _mock_pad_with_hat()
    cases = (((1, 0), 101, "右"), ((-1, 0), 103, "左"),
             ((0, 1), 100, "上"), ((0, -1), 102, "下"))
    for hat, expect, label in cases:
        holder["hat"] = hat
        pad.poll()
        assert pad.buttons.get(expect) is True, ("%s %s -> %r" % (label, hat, pad.buttons))
        others = {100, 101, 102, 103} - {expect}
        assert not any(pad.buttons.get(i) for i in others), (hat, pad.buttons)

    holder["hat"] = (1, 1)                  # 斜向：两个方向同时按
    pad.poll()
    assert pad.buttons.get(101) and pad.buttons.get(100), pad.buttons

    holder["hat"] = (0, 0)                  # 松手
    pad.poll()
    assert not any(pad.buttons.get(i) for i in (100, 101, 102, 103)), pad.buttons
    print("PASS 十字键 hat -> 虚拟索引（右101/左103/上100/下102，含斜向与松手）")


def test_dpad_hat_drives_fastforward():
    """端到端：真实十字键读数 -> 快进/快退方向键。"""
    pad, holder = _mock_pad_with_hat()
    cfg = mk({
        "101": {"action": "key", "mode": "tap", "hz": 6, "key": "right"},
        "103": {"action": "key", "mode": "tap", "hz": 6, "key": "left"},
    })
    r = Rec(); e = G.Engine(cfg, r); e.start()

    holder["hat"] = (1, 0)                  # 推右
    pad.poll(); e.update(dict(pad.buttons))
    holder["hat"] = (0, 0)                  # 松手
    pad.poll(); e.update(dict(pad.buttons))
    assert r.of("keytap") == [("keytap", 0x27)], r.events

    r.events = []
    holder["hat"] = (-1, 0)                 # 推左
    pad.poll(); e.update(dict(pad.buttons))
    holder["hat"] = (0, 0)
    pad.poll(); e.update(dict(pad.buttons))
    assert r.of("keytap") == [("keytap", 0x25)], r.events
    print("PASS 端到端 十字键右 -> →(0x27) / 左 -> ←(0x25)")


def test_dpad_release_key_vanishes():
    """回归（真凶）：真实 poll() 松开十字键时，那个按钮键是**从字典里消失**，
    不是变成 False —— 因为 hat 只在有方向时才往 buttons 里塞键。

    引擎若只遍历「本帧存在的键」，就永远看不到下降沿：
      tap  模式 -> 只有第一次按生效，之后再按全哑（快进「经常无效」的真凶）
      hold 模式 -> 松开不释放，键一直按住
    所以引擎必须把「上一帧有、本帧没有」的键当成已松开。
    """
    pad, holder = _mock_pad_with_hat()
    cfg = mk({"101": {"action": "key", "mode": "tap", "hz": 20, "key": "right"},
              "103": {"action": "key", "mode": "tap", "hz": 20, "key": "left"}})
    r = Rec(); e = G.Engine(cfg, r); e.start()

    for i in range(3):                       # 连按三次「右」
        holder["hat"] = (1, 0)
        pad.poll(); e.update(dict(pad.buttons))     # 按下
        holder["hat"] = (0, 0)
        pad.poll(); e.update(dict(pad.buttons))     # 松手：101 这个键直接不见了
    assert len(r.of("keytap")) == 3, \
        "连按三次十字键右应发 3 次方向键, 实际 %d 次: %r" % (len(r.of("keytap")), r.events)

    r.events = []
    for i in range(2):                       # 换「左」再连按两次
        holder["hat"] = (-1, 0)
        pad.poll(); e.update(dict(pad.buttons))
        holder["hat"] = (0, 0)
        pad.poll(); e.update(dict(pad.buttons))
    assert len(r.of("keytap")) == 2, r.events
    assert all(vk == 0x25 for _, vk in r.of("keytap")), r.events
    print("PASS 十字键松开后仍能再次触发（右连按3次=3 / 左连按2次=2）")


def test_dpad_hold_release_key_vanishes():
    """hold 模式：hat 松开时键消失，也必须触发释放，不能一直按着。"""
    pad, holder = _mock_pad_with_hat()
    cfg = mk({"101": {"action": "key", "mode": "hold", "hz": 20, "key": "right"}})
    r = Rec(); e = G.Engine(cfg, r); e.start()

    holder["hat"] = (1, 0)
    pad.poll(); e.update(dict(pad.buttons))          # 按下
    holder["hat"] = (0, 0)
    pad.poll(); e.update(dict(pad.buttons))          # 松手（键消失）
    assert r.of("keydown") == [("keydown", 0x27)], r.events
    assert r.of("keyup") == [("keyup", 0x27)], \
        "松开十字键必须释放, 实际 %r" % r.events
    print("PASS 十字键 hold 松开（键消失）会正确释放")


def test_dpad_rapid_stops_when_key_vanishes():
    """rapid 模式：hat 松开（键消失）后必须停，不能继续连发。"""
    pad, holder = _mock_pad_with_hat()
    cfg = mk({"101": {"action": "key", "mode": "rapid", "hz": 50, "key": "right"}})
    r = Rec(); e = G.Engine(cfg, r); e.start()

    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.2:
        holder["hat"] = (1, 0)
        pad.poll(); e.update(dict(pad.buttons))
        time.sleep(0.005)
    holder["hat"] = (0, 0)
    pad.poll(); e.update(dict(pad.buttons))          # 松手（键消失）
    n = len(r.of("keytap"))
    assert n > 0, r.events
    for _ in range(20):
        e.update({})                                  # 再喂几帧
        time.sleep(0.01)
    assert len(r.of("keytap")) == n, "松手后不应继续连发: %r" % r.events
    print("PASS 十字键 rapid 松手（键消失）即停（%d 次）" % n)


def test_key_combo_action():
    cfg = mk({"5": {"action": "key_combo", "mode": "tap", "hz": 20, "key": "ctrl+c"}})
    r = Rec(); e = G.Engine(cfg, r); e.start()
    e.update({5: True}); e.update({5: False})
    assert r.of("keytap") == [("keytap", 0x43)], r.events
    assert r.of("keydown") == [("keydown", 0xA2)], r.events
    print("PASS 组合键动作（Ctrl+C）")


def test_win_key_plain_vk():
    """Win 键必须走「纯 VK、不带扫描码、不带扩展标志」。

    实测（Windows 11 26200）：带扫描码时系统完全收不到 Win 组合键，
    Win+R 打不开运行框、Win+H 唤不出语音输入。这条是防回归的守门测试。
    """
    sim = G.InputSimulator.__new__(G.InputSimulator)   # 不走 __init__，不发真实按键
    sim.scancode_mode = True
    sim.enabled = True
    got = []
    sim._send = lambda *inp: (got.append(inp[0]), 1)[1]

    sim._key(0x5B, False)                    # 左 Win 按下
    ki = got[-1].ki
    assert ki.wVk == 0x5B
    assert ki.wScan == 0, "Win 键不应带扫描码，实际 wScan=%d" % ki.wScan
    assert not (ki.dwFlags & 0x0001), "Win 键不应带 EXTENDEDKEY"
    assert not (ki.dwFlags & 0x0002), "按下不应带 KEYUP"

    sim._key(0x5C, True)                     # 右 Win 抬起
    ki = got[-1].ki
    assert ki.wScan == 0 and not (ki.dwFlags & 0x0001)
    assert ki.dwFlags & 0x0002, "抬起必须带 KEYUP"

    sim._key(0x48, False)                    # 对照：普通按键 H
    ki = got[-1].ki
    assert ki.dwFlags & 0x0008, "普通键应保留扫描码模式"
    assert ki.wScan != 0, "普通键应当有扫描码"

    sim._key(0x25, False)                    # 对照：方向键（需要扩展标志）
    ki = got[-1].ki
    assert ki.dwFlags & 0x0001, "方向键这类系统键应带扩展标志"
    print("PASS Win 键走纯 VK（不带扫描码/扩展标志），普通键仍是老样子")


def test_poll_resilience():
    """poll() 必须逐项容错：单次读取失败不能整帧丢输入；句柄全废时要能自愈不崩。"""
    pad = G.Gamepad.__new__(G.Gamepad)      # 不走 __init__，不真的初始化 pygame
    pad.available, pad.pygame, pad._pump_ok = True, None, False
    pad.nbuttons, pad.naxes, pad.nhats = 3, 2, 1
    pad.buttons, pad.axes, pad.hats = {}, [], []
    pad.error = pad.last_error = ""
    pad.rescan = lambda: None

    class JS(object):
        def get_button(self, i):
            return i == 1

        def get_axis(self, i):
            return 0.5

        def get_hat(self, i):
            return (0, 0)

    pad.js = JS(); pad.poll()
    assert pad.buttons == {0: False, 1: True, 2: False}, pad.buttons
    assert pad.axes == [0.5, 0.5], pad.axes
    assert pad.hats == [(0, 0)], pad.hats

    class JS2(JS):
        def get_button(self, i):
            if i == 2:
                raise RuntimeError("boom")
            return i == 1

    pad.js = JS2(); pad.poll()
    assert pad.buttons.get(1) is True and 2 not in pad.buttons, pad.buttons
    assert len(pad.buttons) == 2, pad.buttons

    class JS3(JS):
        def get_button(self, i):
            raise RuntimeError("dead handle")

    pad.js = JS3(); pad.poll()          # 不应抛异常
    assert pad.buttons == {}, pad.buttons
    assert pad.last_error, "应记录句柄失效"
    print("PASS poll 逐项容错 + 句柄失效自愈")


def test_key_resolve():
    assert G.key_to_vk("a") == 0x41
    assert G.key_to_vk("f5") == 0x74
    assert G.key_to_vk("space") == 0x20
    assert G.key_to_vk("vk:65") == 65
    assert G.key_to_vk("F12") == 0x7B
    assert G.key_to_vk("left") == 0x25      # 快退
    assert G.key_to_vk("right") == 0x27     # 快进
    assert G.key_to_vk("left") in G.EXTENDED_VKS, "方向键必须走扩展标志，否则系统当成小键盘 4/6"
    assert G.vk_to_key_name(0x20) == "space"
    assert G.vk_to_key_name(0x27) == "right"
    print("PASS 按键名解析（含方向键 left/right）")

def test_config_roundtrip():
    import tempfile, os
    cfg = G.default_config()
    p = os.path.join(tempfile.gettempdir(), "gm_test.json")
    G.save_config(cfg, p)
    back = G.load_config(p)
    assert back["buttons"]["0"]["action"] == "mouse_left"
    os.remove(p)
    print("PASS 配置读写")


# ---------- 手柄「待机后假连接」自愈 ----------

class _FakeXI(object):
    """XInput 探针替身：可编程返回「连了哪个槽位 / 有没有按键」。"""
    available = True

    def __init__(self, slot, buttons=0, usable=True):
        self.slot, self.buttons, self.usable = slot, buttons, usable

    def read(self):
        if not self.usable:
            return None, None          # 探针不可用
        if self.slot is None:
            return None, {}            # 明确「一个都没连」
        return self.slot, {"packet": 1, "buttons": self.buttons}


def _mkpad(name, xi, seen=False):
    p = G.Gamepad.__new__(G.Gamepad)
    p.js = object()                    # 假装握着句柄
    p.name = name
    p.xinput = xi
    p.stale = False
    p._stale_since = 0.0
    p._xinput_seen = seen
    p.last_error = ""
    return p


XBOX_NAME = "Controller (XBOX 360 For Windows)"


def test_stale_xinput_says_no_device():
    """XInput 说一个都没连、SDL 却说连着 → 持续后判定为假连接。"""
    p = _mkpad(XBOX_NAME, _FakeXI(None), seen=True)
    p._check_stale({})
    assert p.stale is False, "第一帧只记时间，不该立刻下结论"
    p._stale_since = time.time() - 1.0
    p._check_stale({})
    assert p.stale is True, "异常持续超过确认时间后应判定假连接"
    assert p.last_error
    print("PASS 假连接判定：XInput 看不见设备")


def test_stale_requires_prior_connection():
    """从没被 XInput 看见过的手柄（可能本就不支持 XInput）不能误判。"""
    p = _mkpad(XBOX_NAME, _FakeXI(None), seen=False)
    p._stale_since = time.time() - 5.0
    p._check_stale({})
    assert p.stale is False, "没有'曾经连过'的证据就不该下结论"
    print("PASS 假连接判定：缺乏证据时保持沉默")


def test_stale_xinput_has_buttons_sdl_dead():
    """XInput 有按键、SDL 一个键都没收到 → 句柄失效。"""
    p = _mkpad(XBOX_NAME, _FakeXI(0, buttons=0x1000))
    p._check_stale({})
    assert p.stale is False, "单帧不判定"
    p._stale_since = time.time() - 1.0
    p._check_stale({})
    assert p.stale is True
    print("PASS 假连接判定：XInput 有按键而 SDL 死寂")


def test_stale_never_false_positive_on_idle():
    """手柄静止时轴读数乱跳，也绝不能被判成假连接（本机克隆手柄实测如此）。"""
    for _ in range(50):
        p = _mkpad(XBOX_NAME, _FakeXI(0, buttons=0))
        p._stale_since = time.time() - 3.0
        p._check_stale({})
        assert p.stale is False, "静止 + 轴漂移不该触发误报"
    print("PASS 假连接判定：静止/轴漂移免疫")


def test_stale_ignores_non_xbox_and_unavailable_probe():
    p = _mkpad("Generic USB Joystick", _FakeXI(None), seen=True)
    p._stale_since = time.time() - 5.0
    p._check_stale({})
    assert p.stale is False, "非 Xbox 手柄不参与判定"
    p = _mkpad(XBOX_NAME, _FakeXI(None, usable=False), seen=True)
    p._stale_since = time.time() - 5.0
    p._check_stale({})
    assert p.stale is False, "探针不可用时不得下结论"
    print("PASS 假连接判定：只对 Xbox 类手柄、且探针可用时才生效")


class _FakePad(object):
    available = True

    def __init__(self, connected=True, stale=False):
        self.connected, self.stale = connected, stale
        self.calls = []

    def rescan(self):
        self.calls.append("rescan")
        self.stale = False
        return 1

    def deep_reset(self):
        self.calls.append("deep_reset")
        self.stale = False
        return 1


def test_supervise_pad_ladder():
    """假连接：先轻量重扫，再升级重建；并遵守退避。"""
    pad = _FakePad(connected=True, stale=True)
    st = {}
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan"], pad.calls
    pad.stale = True
    st["next_recover"] = 0.0
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan", "deep_reset"], pad.calls
    pad.stale = True
    st["next_recover"] = time.time() + 5.0
    n = len(pad.calls)
    G.supervise_pad(pad, st)
    assert len(pad.calls) == n, "退避期内不该再动手"
    print("PASS 守护策略：重扫 → 重建 pygame → 退避")


def test_supervise_pad_other_states():
    """未连接：每 2 秒扫一次；正常空闲：心跳重枚举；有输入：不打扰。"""
    pad = _FakePad(connected=False, stale=False)
    st = {}
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan"], pad.calls
    st["last_scan"] = time.time()
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan"], "2 秒内不该重复扫"

    pad = _FakePad(connected=True, stale=False)
    st = {"last_input": time.time() - 30, "last_idle": time.time() - 30}
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan"], "长时间空闲应心跳重枚举"
    st["last_idle"] = time.time()
    G.supervise_pad(pad, st)
    assert pad.calls == ["rescan"], "不该每帧都重枚举"

    pad = _FakePad(connected=True, stale=False)
    st = {"last_input": time.time(), "last_idle": 0.0}
    G.supervise_pad(pad, st)
    assert pad.calls == [], "正在使用手柄时不该动它"
    print("PASS 守护策略：未连接/空闲/使用中三种情况")


def test_pad_input_seen():
    class _P(object):
        buttons = {0: False}
        axes = [0.0, 0.0]
    assert G.pad_input_seen(_P()) is False
    _P.buttons = {0: True}
    assert G.pad_input_seen(_P()) is True
    _P.buttons = {0: False}
    _P.axes = [0.0, 0.9]
    assert G.pad_input_seen(_P()) is True
    print("PASS pad_input_seen：按键/摇杆/静止")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            fail += 1
            print("FAIL %s -> %s" % (t.__name__, exc))
        except Exception as exc:
            fail += 1
            print("ERROR %s -> %r" % (t.__name__, exc))
    print("-" * 46)
    print("共 %d 项，失败 %d 项" % (len(tests), fail))
    sys.exit(1 if fail else 0)
