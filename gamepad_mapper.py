#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gamepad Mapper  --  手柄当无线键盘 / 鼠标
=================================================================
把任意手柄（XBox / PS4 / PS5 / Switch Pro / 杂牌 DirectInput 手柄）
变成一套完整的键盘 + 鼠标，支持：

  * 鼠标左键 / 右键 / 中键 单击
  * 鼠标双击（间隔可调）
  * 连点（按住不放 -> 无限自动点击，最高 100 次/秒）
  * 连发任意键盘按键（按住不放持续触发）
  * 键盘按键单击 / 按住不放
  * 滚轮上下、十字键、摇杆当鼠标
  * 一键开关映射（手柄按钮 / Ctrl+F12 全局热键）

用法:
    python gamepad_mapper.py            打开图形控制台（推荐）
    python gamepad_mapper.py --nogui    无界面，直接读 config.json 运行
    python gamepad_mapper.py --list     列出手柄
    python gamepad_mapper.py --check    环境自检

依赖: pygame    (pip install pygame)
平台: Windows   (输入使用 SendInput)
"""

import ctypes
import json
import os
import sys
import time

APP_NAME = "Gamepad Mapper"
if getattr(sys, "frozen", False):
    # PyInstaller 单文件模式：__file__ 指向临时解压目录，改用 exe 所在目录
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DPAD_BASE = 100
DPAD_NAMES = ["方向键↑", "方向键→", "方向键↓", "方向键←"]

IS_WINDOWS = sys.platform.startswith("win")
MAX_RAPID_HZ = 100.0
DEFAULT_PORT = 8765


# ============================================================================
# 1. Windows SendInput
# ============================================================================

if IS_WINDOWS:
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR))

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR))

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = (("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD))

    class _INPUTUNION(ctypes.Union):
        _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = (("type", wintypes.DWORD), ("u", _INPUTUNION))

    _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    _user32.SendInput.restype = wintypes.UINT
    _SendInput = _user32.SendInput

    MOVE = 0x0001
    LEFTDOWN = 0x0002
    LEFTUP = 0x0004
    RIGHTDOWN = 0x0008
    RIGHTUP = 0x0010
    MIDDLEDOWN = 0x0020
    MIDDLEUP = 0x0040
    WHEEL = 0x0800

    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008

    _MapVirtualKeyW = _user32.MapVirtualKeyW
    _MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    _MapVirtualKeyW.restype = wintypes.UINT
    _GetAsyncKeyState = _user32.GetAsyncKeyState
    _GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _GetAsyncKeyState.restype = ctypes.c_short


# ============================================================================
# 2. 虚拟键码表
# ============================================================================

VK_TABLE = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0x10, "ctrl": 0x11,
    "alt": 0x12, "pause": 0x13, "capslock": 0x14, "esc": 0x1B, "space": 0x20,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
    "lwin": 0x5B, "rwin": 0x5C, "apps": 0x5D,
    "numpad0": 0x60, "numpad1": 0x61, "numpad2": 0x62, "numpad3": 0x63,
    "numpad4": 0x64, "numpad5": 0x65, "numpad6": 0x66, "numpad7": 0x67,
    "numpad8": 0x68, "numpad9": 0x69,
    "multiply": 0x6A, "add": 0x6B, "separator": 0x6C, "subtract": 0x6D,
    "decimal": 0x6E, "divide": 0x6F,
    "numlock": 0x90, "scrolllock": 0x91,
    "lshift": 0xA0, "rshift": 0xA1, "lctrl": 0xA2, "rctrl": 0xA3,
    "lalt": 0xA4, "ralt": 0xA5,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}
for _i in range(1, 25):
    VK_TABLE["f%d" % _i] = 0x6F + _i

VK_TO_NAME = {}
for _n, _v in VK_TABLE.items():
    VK_TO_NAME.setdefault(_v, _n)

EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D,
                0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0xA3, 0xA5}

# 左右 Win 键必须用「纯 VK、不带 EXTENDEDKEY」发送。
# 实测（Windows 11 26200）：这三种方式里只有最后一种能让 Win+R 真的弹出运行框——
#   扫描码 + 扩展标志  -> 无效
#   扫描码、无扩展标志 -> 无效
#   纯 VK、无扩展标志  -> 有效
# 带扫描码时系统收不到 Win 组合键，所以 Win+H（语音输入）之类会完全没反应。
VK_VK_ONLY = {0x5B, 0x5C}

_KEYSYM_ALIAS = {
    "return": "enter", "escape": "esc", "prior": "pageup", "next": "pagedown",
    "caps_lock": "capslock", "control_l": "ctrl", "control_r": "rctrl",
    "shift_l": "shift", "shift_r": "rshift", "alt_l": "alt", "alt_r": "ralt",
    "super_l": "lwin", "super_r": "rwin",
    "kp_0": "numpad0", "kp_1": "numpad1", "kp_2": "numpad2", "kp_3": "numpad3",
    "kp_4": "numpad4", "kp_5": "numpad5", "kp_6": "numpad6", "kp_7": "numpad7",
    "kp_8": "numpad8", "kp_9": "numpad9",
}


def key_to_vk(key):
    """'a' / 'f5' / 'space' / 'vk:65' -> 虚拟键码"""
    if key is None:
        return None
    if isinstance(key, int):
        return key
    k = str(key).strip().lower()
    if not k:
        return None
    if k.startswith("vk:"):
        try:
            return int(k[3:])
        except ValueError:
            return None
    if k in VK_TABLE:
        return VK_TABLE[k]
    if k in _KEYSYM_ALIAS:
        return VK_TABLE.get(_KEYSYM_ALIAS[k])
    if len(k) == 1:
        for name, vk in VK_TABLE.items():
            if len(name) == 1 and name.upper() == k.upper():
                return vk
        code = ord(k.upper())
        if 0x30 <= code <= 0x5A:
            return code
    return None


def vk_to_key_name(vk):
    if vk is None:
        return ""
    return VK_TO_NAME.get(vk, "vk:%d" % vk)


# 组合键里修饰键的别名（'win+h' / 'ctrl+shift+k' / 'cmd+r' 都能认）
MOD_ALIAS = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift", "alt": "alt",
    "win": "lwin", "windows": "lwin", "meta": "lwin", "super": "lwin",
    "cmd": "lwin", "command": "lwin",
    "lwin": "lwin", "rwin": "rwin",
    "lctrl": "lctrl", "rctrl": "rctrl",
    "lshift": "lshift", "rshift": "rshift",
    "lalt": "lalt", "ralt": "ralt",
}

# 修饰键归一化：'ctrl' 之类不带左右时统一按左侧发
MOD_NORMALIZE = {"ctrl": "lctrl", "shift": "lshift", "alt": "lalt"}


def parse_key_spec(spec):
    """把按键描述解析成 (修饰键 vk 列表, 主键 vk)。

    'win+h'        -> ([0x5B], 0x48)
    'ctrl+shift+k' -> ([0xA2, 0xA0], 0x4B)
    'a'            -> ([], 0x41)
    """
    if not spec:
        return [], None
    parts = [p.strip().lower() for p in str(spec).split("+") if p.strip()]
    if not parts:
        return [], None
    if len(parts) == 1:
        return [], key_to_vk(parts[0])
    main = key_to_vk(parts[-1])
    mods = []
    for raw in parts[:-1]:
        name = MOD_ALIAS.get(raw, raw)
        name = MOD_NORMALIZE.get(name, name)
        vk = key_to_vk(name)
        if vk is not None and vk not in mods:
            mods.append(vk)
    return mods, main


def key_spec_display(spec):
    """组合键的显示名（日志/面板上用，好看一点）：'win+h' -> 'Win+H'"""
    mods, vk = parse_key_spec(spec)
    if vk is None:
        return ""
    nice = {"lctrl": "Ctrl", "rctrl": "Ctrl", "lshift": "Shift", "rshift": "Shift",
            "lalt": "Alt", "ralt": "Alt", "lwin": "Win", "rwin": "Win"}

    def one(v):
        n = vk_to_key_name(v)
        if n in nice:
            return nice[n]
        return n.upper() if len(n) == 1 else n

    return "+".join([one(m) for m in mods] + [one(vk)])


# ============================================================================
# 3. 输入模拟器
# ============================================================================

class InputSimulator(object):
    """用 SendInput 模拟鼠标与键盘（游戏里也生效）。"""

    def __init__(self, scancode_mode=True):
        self.scancode_mode = scancode_mode
        self._held_keys = set()
        self.enabled = IS_WINDOWS
        self.stats = {"clicks": 0, "keys": 0, "scrolls": 0}

    def _send(self, *inputs):
        if not self.enabled or not inputs:
            return 0
        arr = (INPUT * len(inputs))(*inputs)
        return _SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def probe(self):
        """注入一个无害的 F24 按键（按下+抬起），返回系统实际接受的事件数。
        用来确认 SendInput 真的能被系统接收，而不是只看一个布尔标志。"""
        if not self.enabled:
            return 0, 0
        vk = VK_TABLE["f24"]
        scan = _MapVirtualKeyW(vk, 0)
        made = 0
        for up in (False, True):
            flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
            inp = INPUT(type=1)
            inp.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
            made += self._send(inp)
        return made, 2

    def _mouse(self, flags, dx=0, dy=0, data=0):
        inp = INPUT(type=0)
        inp.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
        self._send(inp)

    def _key(self, vk, up=False):
        inp = INPUT(type=1)
        scan = 0
        flags = 0
        plain = vk in VK_VK_ONLY          # Win 键只走纯 VK，见 VK_VK_ONLY 注释
        if self.scancode_mode and not plain:
            scan = _MapVirtualKeyW(vk, 0)
            if scan:
                flags |= KEYEVENTF_SCANCODE
        if not plain and vk in EXTENDED_VKS:
            flags |= KEYEVENTF_EXTENDEDKEY
        if up:
            flags |= KEYEVENTF_KEYUP
        inp.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        self._send(inp)

    # ---- 鼠标 ----
    def mouse_down(self, btn="left"):
        self._mouse({"left": LEFTDOWN, "right": RIGHTDOWN, "middle": MIDDLEDOWN}[btn])

    def mouse_up(self, btn="left"):
        self._mouse({"left": LEFTUP, "right": RIGHTUP, "middle": MIDDLEUP}[btn])

    def click(self, btn="left"):
        self.mouse_down(btn)
        self.mouse_up(btn)
        self.stats["clicks"] += 1

    def double_click(self, btn="left", gap=0.04):
        self.click(btn)
        time.sleep(gap)
        self.click(btn)

    def move(self, dx, dy):
        if dx or dy:
            self._mouse(MOVE, int(dx), int(dy))

    def scroll(self, notches):
        if not notches:
            return
        self._mouse(WHEEL, 0, 0, int(120 * notches) & 0xFFFFFFFF)
        self.stats["scrolls"] += abs(int(notches))

    # ---- 键盘 ----
    def key_down(self, vk):
        if vk is None:
            return
        self._key(vk, up=False)
        self._held_keys.add(vk)

    def key_up(self, vk):
        if vk is None:
            return
        self._key(vk, up=True)
        self._held_keys.discard(vk)

    def key_tap(self, vk):
        if vk is None:
            return
        self.key_down(vk)
        self.key_up(vk)
        self.stats["keys"] += 1

    def combo_tap(self, spec):
        """按一次组合键，例如 'win+h'（Windows 语音输入）。

        修饰键必须先按下、主键抬起后再按相反顺序释放，
        否则部分程序（尤其系统的热键处理）收不到这个组合。
        """
        mods, vk = parse_key_spec(spec)
        if vk is None:
            return
        for m in mods:
            self.key_down(m)
        try:
            self.key_tap(vk)
        finally:
            for m in reversed(mods):
                self.key_up(m)

    def release_all(self):
        for vk in list(self._held_keys):
            self.key_up(vk)
        self._held_keys.clear()


# ============================================================================
# 4. 手柄读取 (pygame)
# ============================================================================

# --- 「假连接」自愈 ---------------------------------------------------------
# 症状：手柄长时间待机（或电脑睡眠唤醒）后按什么都没反应，连重启本程序都没用。
# 原因：设备节点在 Windows 里还挂着，SDL/pygame 又打开了一个**已经失效的句柄**，
#       get_button() 照样正常返回（全是 False），于是程序永远以为「已连接」，
#       也就永远不去重连 —— 而重启程序只是把同一个坏节点重新打开一遍。
#
# 判断办法：XInput 走的是 XUSB 驱动，和 SDL 的 HIDAPI 是两条完全独立的路径。
# 把手柄当"测谎仪"用来交叉验证：
#   · XInput 说「一个槽位都没连通」而 SDL 说「已连接」 → SDL 是假连接
#   · XInput 有按键动作、SDL 却一片死寂            → SDL 句柄已失效
STALE_CONFIRM_SECONDS = 0.6    # 上述异常要持续这么久才认定，避免误判
STALE_RETRY_SECONDS = 1.5      # 假连接时两次自愈尝试的间隔
IDLE_RESCAN_SECONDS = 6.0      # 连续空闲这么久，就顺手重枚举一次手柄


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XInputProbe(object):
    """只读探针：Windows 上 Xbox 类手柄"是不是真的在连着"。

    非 Windows 或系统没有 xinput DLL 时永远 available=False，此时所有判断都会
    被跳过（绝不能让探针本身成为误判来源）。
    """

    def __init__(self):
        self.dll = None
        self.fn = None
        if os.name != "nt":
            return
        for dll_name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                dll = ctypes.WinDLL(dll_name)
                fn = dll.XInputGetState
                fn.argtypes = [ctypes.c_ulong, ctypes.POINTER(_XINPUT_STATE)]
                fn.restype = ctypes.c_ulong
                self.dll, self.fn = dll, fn
                break
            except Exception:
                continue

    @property
    def available(self):
        return self.fn is not None

    def read(self):
        """返回 (slot, state)。

        slot=None + state=None → 探针不可用，调用方不要下结论；
        slot=None + state={}   → 探针可用，且明确「没有任何手柄连通」；
        slot=0..3             → 该槽位连通，state 里带 buttons / active。
        """
        if self.fn is None:
            return None, None
        for slot in range(4):
            st = _XINPUT_STATE()
            try:
                rc = self.fn(slot, ctypes.byref(st))
            except Exception:
                return None, None
            if rc == 0:
                # 只用 wButtons 判断"有没有动作"，轴一律不参与比对：
                # 实测这只克隆手柄的摇杆在 XInput 里静止时读数在 ±29000 乱跳，
                # 而 SDL 里读到的是 0 —— 两者轴映射完全不同，拿轴比对必然误判。
                return slot, {"packet": st.dwPacketNumber,
                              "buttons": st.wButtons}
        return None, {}


class Gamepad(object):
    """轮询手柄状态。buttons 用虚拟索引，十字键在 100+。"""

    def __init__(self):
        self.available = False
        self.error = ""
        self.last_error = ""
        self.pygame = None
        self.names = []
        self.index = 0
        self.js = None
        self.nbuttons = 16
        self.naxes = 6
        self.nhats = 1
        self.name = ""
        self.buttons = {}
        self.axes = []
        self.hats = []
        self._pump_ok = False
        self.xinput = XInputProbe()
        self.stale = False          # True = 句柄假连接（XInput 判定）
        self.recover_count = 0      # 累计自愈次数（面板上显示）
        self._stale_since = 0.0
        self._xinput_seen = False   # 本次运行中 XInput 是否至少连通过一次
        self._init_pygame()

    def _init_pygame(self):
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame
            self.pygame = pygame
        except Exception as exc:
            self.error = ("缺少 pygame：%s\n请先安装：  pip install pygame" % exc)
            return
        # 让 SDL 在没有窗口 / 窗口失焦时也照常处理手柄（后台常驻时更稳）。
        # 必须在 pygame.init() 之前设置，SDL 初始化时会读这个 hint。
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        try:
            self.pygame.init()
            self.pygame.joystick.init()
        except Exception as exc:
            self.error = "pygame 初始化失败：%s" % exc
            return
        if not self._start_events():
            return
        self.available = True
        self.rescan()

    def _start_events(self):
        """启动 SDL 事件子系统。

        没有窗口时 event.pump() 可能直接报错，就退化成开一个 1x1 的隐藏窗口；
        两种都不行才算失败。deep_reset() 重建 pygame 后需要重跑这一段。
        """
        try:
            self.pygame.event.pump()
            self._pump_ok = True
            return True
        except Exception:
            pass
        try:
            self.pygame.display.init()
            self.pygame.display.set_mode(
                (1, 1), getattr(self.pygame, "HIDDEN", 0))
            self.pygame.event.pump()
            self._pump_ok = True
            return True
        except Exception as exc:
            self.error = "SDL 事件子系统不可用：%s" % exc
            return False

    def _count(self):
        try:
            return self.pygame.joystick.get_count()
        except Exception:
            return 0

    def rescan(self):
        if not self.available:
            return 0
        # 关键：先把旧句柄丢掉再 quit。不丢的话 SDL 内部仍持有那个已经失效的
        # 设备对象，quit/init 之后拿回来的还是同一个坏句柄 —— 重扫等于白扫，
        # 这正是「待机后没反应、重启程序也没用」的原因。
        old = self.js
        self.js = None
        self._stale_since = 0.0
        try:
            del old
        except Exception:
            pass
        try:
            self.pygame.joystick.quit()
            self.pygame.joystick.init()
        except Exception:
            pass
        n = self._count()
        self.names = []
        for i in range(n):
            try:
                j = self.pygame.joystick.Joystick(i)
                try:
                    j.init()
                except Exception:
                    pass
                self.names.append(j.get_name())
            except Exception:
                self.names.append("手柄 %d" % i)
        if n == 0:
            self.js = None
            self.name = ""
            self.nbuttons, self.naxes, self.nhats = 16, 6, 1
            self.buttons, self.axes, self.hats = {}, [], []
            return 0
        self.open(min(self.index, n - 1))
        return n

    def open(self, index):
        try:
            j = self.pygame.joystick.Joystick(index)
            try:
                j.init()
            except Exception:
                pass
            self.js = j
            self.index = index
            self.name = j.get_name()
            self.nbuttons = max(j.get_numbuttons(), 0)
            self.naxes = max(j.get_numaxes(), 0)
            self.nhats = max(j.get_numhats(), 0)
            return True
        except Exception as exc:
            self.js = None
            self.error = "打开手柄失败：%s" % exc
            return False

    def deep_reset(self):
        """动大手术：把 pygame（连带 SDL 手柄子系统）整个拆掉重建，再重新枚举。

        rescan() 救不回来时用它 —— 特别是「SDL 连设备都枚举不到、XInput 明明
        说手柄在线」那种情况（SDL 的枚举缓存已经烂了，只有整栈重建才认新设备）。
        """
        if self.pygame is None:
            return 0
        self.recover_count += 1
        self.js = None
        self._stale_since = 0.0
        self.stale = False
        try:
            self.pygame.joystick.quit()
        except Exception:
            pass
        try:
            self.pygame.quit()
        except Exception:
            pass
        try:
            time.sleep(0.25)     # 给驱动一点时间真正释放设备
        except Exception:
            pass
        try:
            self.pygame.init()
            self.pygame.joystick.init()
        except Exception as exc:
            self.error = "pygame 重新初始化失败：%s" % exc
            return 0
        if not self._start_events():
            return 0
        self.available = True
        n = self.rescan()
        if n:
            self.last_error = ""
        return n

    def _is_xbox_like(self):
        n = (self.name or "").lower()
        return ("xbox" in n) or ("xinput" in n) or ("360" in n)

    def _check_stale(self, buttons):
        """用 XInput 交叉验证 SDL 读数，判断当前句柄是不是「假连接」。

        只在「手柄名像 Xbox + XInput 探针可用」时才下结论，避免误伤杂牌手柄；
        并且要求异常持续 STALE_CONFIRM_SECONDS，防止偶发抖动引发误判。
        """
        self.stale = False
        # getattr 兜底：测试里会用 __new__ 直接构造 Gamepad（不走 __init__）
        probe = getattr(self, "xinput", None)
        if self.js is None or probe is None or not probe.available \
                or not self._is_xbox_like():
            self._stale_since = 0.0
            return

        xslot, xstate = probe.read()
        if xstate is None:                  # 探针本身不可用 → 不下结论
            self._stale_since = 0.0
            return

        bad = False
        if xslot is None:
            # XInput 明确说「一个手柄都没连」，SDL 却还"连着"。
            # 只有本次运行中确实连通过，才敢判定是假连接 ——
            # 否则可能只是这只手柄本来就不被 XInput 支持。
            bad = getattr(self, "_xinput_seen", False)
        else:
            self._xinput_seen = True
            # XInput 看到有按键按下、SDL 却一个键都没收到 → 句柄失效。
            # 只看按键位掩码，不看轴：杂牌手柄在两条路径上的轴读数完全对不上。
            if xstate.get("buttons"):
                bad = not any(buttons.values())

        if bad:
            now = time.time()
            since = getattr(self, "_stale_since", 0.0)
            if not since:
                self._stale_since = now
            elif now - since >= STALE_CONFIRM_SECONDS:
                self.stale = True
                self.last_error = ("手柄「假连接」：XInput 能看见它、SDL 收不到输入，"
                                   "正在自动重连…")
        else:
            self._stale_since = 0.0

    @property
    def connected(self):
        return self.js is not None

    def poll(self):
        self.buttons = {}
        self.axes = []
        self.hats = []
        if not self.available or self.js is None:
            return
        try:
            if self._pump_ok:
                self.pygame.event.pump()
        except Exception:
            pass
        # 逐项容错：任何一次读取失败都不该让整帧输入丢失
        buttons = {}
        got = 0
        for i in range(self.nbuttons):
            try:
                buttons[i] = bool(self.js.get_button(i))
                got += 1
            except Exception:
                pass
        axes = []
        for i in range(self.naxes):
            try:
                axes.append(self.js.get_axis(i))
            except Exception:
                axes.append(0.0)
        hats = []
        for i in range(self.nhats):
            try:
                hats.append(self.js.get_hat(i))
            except Exception:
                hats.append((0, 0))

        if self.nbuttons > 0 and got == 0:
            # 所有按钮都读失败 → 句柄已死。只打标记，交给守护逻辑按退避策略重连；
            # 在这里直接 rescan 会退化成每秒几百次的紧循环。
            self.stale = True
            self.last_error = "手柄句柄已失效，正在自动重连…"
            self.buttons, self.axes, self.hats = {}, [], []
            return
        self.last_error = ""

        self.buttons, self.axes, self.hats = buttons, axes, hats
        self._check_stale(buttons)
        for h, value in enumerate(self.hats):
            hx, hy = value
            base = DPAD_BASE + h * 4
            if hy == 1:
                self.buttons[base + 0] = True
            if hx == 1:
                self.buttons[base + 1] = True
            if hy == -1:
                self.buttons[base + 2] = True
            if hx == -1:
                self.buttons[base + 3] = True

    def button_name(self, idx):
        if idx >= DPAD_BASE:
            hat, d = divmod(idx - DPAD_BASE, 4)
            label = DPAD_NAMES[d]
            return label if self.nhats <= 1 else "%s(%d)" % (label, hat + 1)
        return "按钮 %d" % idx

    def all_button_ids(self):
        ids = list(range(self.nbuttons))
        for h in range(self.nhats):
            ids.extend([DPAD_BASE + h * 4 + d for d in range(4)])
        return ids


def supervise_pad(pad, state):
    """手柄守护：把「未连接 / 假连接 / 长时间空闲」三类情况的重连统一在这里处理。

    state 是一个 dict，用来在两次调用之间保存计时与重试次数。

    这里是本次问题的核心 —— 原来的主循环只在 `pad.connected` 为假时才重扫，
    而「待机假连接」时 connected 永远为真，于是重扫永远不会发生，表现就是
    "按什么都没反应，重启软件也没用"。

    返回 True 表示这次动过手柄（调用方可以顺手刷新面板）。
    """
    if not pad.available:
        return False
    now = time.time()

    # ---- 1) 假连接：重扫 → 重建 pygame，且带退避，别把 CPU 烧了 ----
    if pad.connected and pad.stale:
        if now >= state.get("next_recover", 0.0):
            tries = state.get("tries", 0) + 1
            state["tries"] = tries
            # 第 1 次先轻量重扫；第 2 次起直接重建整个 pygame
            if tries <= 1:
                pad.rescan()
            else:
                pad.deep_reset()
            if tries >= 6:
                # 连试 6 次都没救回来（多半是设备节点在系统层卡死）→ 退避，
                # 面板上会显示"假连接"提示，等用户点「重置手柄驱动」。
                state["tries"] = 0
                state["next_recover"] = now + 12.0
            else:
                state["next_recover"] = now + STALE_RETRY_SECONDS
        return True

    state["tries"] = 0
    state["next_recover"] = 0.0

    # ---- 2) 正常连接：长时间没输入就做一次心跳重枚举 ----
    # 目的是换掉「睡死了但 SDL 自己不知道」的句柄：这种情况 XInput 也可能
    # 一起失联，靠上面的判定抓不到，只能靠定期重枚举兜底。
    if pad.connected:
        if (now - state.get("last_input", 0.0) >= IDLE_RESCAN_SECONDS
                and now - state.get("last_idle", 0.0) >= IDLE_RESCAN_SECONDS):
            state["last_idle"] = now
            pad.rescan()
            return True
        return False

    # ---- 3) 真的没连接：每 2 秒扫一次，等手柄回来 ----
    if now - state.get("last_scan", 0.0) >= 2.0:
        state["last_scan"] = now
        pad.rescan()
        return True
    return False


def pad_input_seen(pad):
    """这一帧有没有手柄输入（用来更新「空闲计时」）。"""
    try:
        if any(pad.buttons.values()):
            return True
    except Exception:
        pass
    try:
        for a in pad.axes:
            if abs(float(a)) > 0.2:
                return True
    except Exception:
        pass
    return False


# ============================================================================
# 5. 动作定义 / 配置
# ============================================================================

ACTION_CHOICES = [
    ("无", "none"),
    ("鼠标左键", "mouse_left"),
    ("鼠标右键", "mouse_right"),
    ("鼠标中键", "mouse_middle"),
    ("鼠标双击", "mouse_double"),
    ("滚轮上", "wheel_up"),
    ("滚轮下", "wheel_down"),
    ("键盘按键", "key"),
    ("组合键", "key_combo"),
    ("语音输入", "voice"),
    ("开关映射", "toggle"),
]
ACTION_IDS = [a for _, a in ACTION_CHOICES]
ACTION_LABELS = {a: n for n, a in ACTION_CHOICES}

# Windows 语音输入（听写）。Win+H 打开/关闭；也可改成
# "win+ctrl+s"（Windows 11 的语音访问）等其它组合。
VOICE_HOTKEY = "win+h"
# 语音输入的最小触发间隔：防止误设成「连发」时把听写面板刷爆
VOICE_MIN_INTERVAL = 0.35

# 连发「启动延迟」默认值(秒)：按下后先等这么久才开始连续补发。
# 作用是把「点一下」和「按住」区分开 —— 没有它，一次快速点按也会连发 2~3 次
# （真实踩过：Y=退格，只想删一个字却删了 3 个）。0.4 接近 Windows 键盘重复延迟的手感。
RAPID_HOLD_DELAY = 0.4

MODE_CHOICES = [
    ("按一下", "tap"),
    ("按住不放", "hold"),
    ("连发(按住不停)", "rapid"),
]
MODE_IDS = [m for _, m in MODE_CHOICES]
MODE_LABELS = {m: n for n, m in MODE_CHOICES}


def default_config():
    """默认映射（XBox 布局，其它手柄按物理编号同理）。"""
    return {
        "enabled": True,
        "rapid_hz": 20.0,
        # 连发启动延迟(秒)：按住超过这么久才开始连续触发。
        # 0.4 = 点一下只触发 1 次、按住 0.4 秒后开始连续（可在面板「连点/连发」里调）
        "rapid_delay": 0.4,
        "double_click_gap": 0.04,
        "hotkey": {"enabled": True, "key": "f12", "ctrl": True},
        # 语音输入用哪个组合键（Windows 语音输入默认 Win+H）
        "voice_hotkey": VOICE_HOTKEY,
        "mouse": {
            "stick": "left",
            "sensitivity": 1400.0,
            "deadzone": 0.18,
            "exponent": 1.6,
            "invert_y": False,
            # 右摇杆当滚轮（旧功能）。默认关掉：滚轮改由十字键↑↓负责，
            # 右摇杆空出来做「低灵敏度移动鼠标」，方便精细瞄准/点小按钮。
            "right_stick_scroll": False,
            # 右摇杆 = 跟左摇杆一样移动鼠标，但灵敏度更低 -> 更好精调。
            "right": {
                "mouse": True,
                # 左摇杆 1400，右摇杆 500（约为它的 1/3）慢且稳
                "sensitivity": 500.0,
                "deadzone": 0.18,
                # 曲线更陡：轻推几乎不动，推深才加速
                "exponent": 1.8,
                "invert_y": False,
            },
            "scroll": {
                # 右摇杆 Y 轴 = 轴 3；向上推 = 向上滚
                "axis": 3,
                # 满推时的速度（格/秒）。6 = 缓慢滚动，适合看文档
                "speed": 6.0,
                # 独立死区，比鼠标摇杆大一点，手一抖不会乱滚
                "deadzone": 0.22,
                # 指数段权重：越大越「轻推几乎不动、推深才快」
                "exponent": 1.9,
                # 线性段权重：保证刚越过死区就有一点缓慢速度，不会「推了没反应」
                "linear_mix": 0.30,
                # 平滑量（0=直通，0.6=很柔和），抑制摇杆抖动
                "smooth": 0.25,
                # 单帧最多滚几格，防止瞬间跳页
                "limit": 4,
                # 勾上则反向：向上推 = 向下滚
                "invert": False,
            },
        },
        "buttons": {
            # A = 鼠标左键。用「按住不放」：快点一下 = 单击，长按 = 左键保持按下（拖拽/框选）。
            # 不要用 tap：tap 只在按下那一瞬间点一下，按住不会有任何持续效果。
            "0": {"action": "mouse_left", "mode": "hold", "hz": 20, "key": ""},
            "1": {"action": "mouse_right", "mode": "tap", "hz": 20, "key": ""},
            "2": {"action": "mouse_double", "mode": "tap", "hz": 20, "key": ""},
            # Y = 键盘退格。用「连发」而不是「按住不放」：SendInput 注入的按键不会触发
            # Windows 自动重复，光按住只会删一格；连发才能「长按连续删除」。
            "3": {"action": "key", "mode": "rapid", "hz": 20, "key": "backspace"},
            "4": {"action": "key", "mode": "tap", "hz": 20, "key": "esc"},
            "5": {"action": "key", "mode": "tap", "hz": 20, "key": "r"},
            "6": {"action": "toggle", "mode": "tap", "hz": 20, "key": ""},
            # Start = 语音输入（Win+H）。按一下开/再按一下关；按住不放 = 按住说/松开停。
            "7": {"action": "voice", "mode": "tap", "hz": 20, "key": ""},
            "8": {"action": "key", "mode": "tap", "hz": 20, "key": "tab"},
            "9": {"action": "key", "mode": "tap", "hz": 20, "key": "enter"},
            "10": {"action": "key", "mode": "tap", "hz": 20, "key": "space"},
            "11": {"action": "key", "mode": "rapid", "hz": 15, "key": "space"},
            "100": {"action": "wheel_up", "mode": "rapid", "hz": 6, "key": ""},
            # 十字键左右 = 快进/快退（→ / ←）。按住连发，视频播放器里就是连续快进。
            "101": {"action": "key", "mode": "tap", "hz": 1.2, "key": "right"},
            "102": {"action": "wheel_down", "mode": "rapid", "hz": 6, "key": ""},
            "103": {"action": "key", "mode": "tap", "hz": 1.2, "key": "left"},
        },
    }


def _deep_merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=CONFIG_PATH):
    cfg = default_config()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                _deep_merge(cfg, user)
        except Exception as exc:
            print("[warn] 读取配置失败，使用默认值：%s" % exc)
    cfg.pop("_scroll_acc", None)
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ============================================================================
# 6. 映射引擎
# ============================================================================

class Engine(object):
    """手柄状态 -> 鼠标 / 键盘动作。"""

    def __init__(self, cfg, sim=None):
        self.cfg = cfg
        self.sim = sim or InputSimulator()
        self.enabled = bool(cfg.get("enabled", True))
        self.on_toggle = None
        self.log = None
        self.running = False
        self._btn_prev = {}
        self._rapid_next = {}
        self._down_state = {}
        self._hotkey_prev = False
        self._last_t = time.perf_counter()
        self._voice_last = 0.0
        # 摇杆滚轮的累积器 / 平滑器
        self._scroll_acc = 0.0
        self._scroll_smooth = 0.0
        self.scroll_rate = 0.0    # 当前滚动速率(格/秒),给面板显示

    # ---- 配置 ----
    @property
    def mappings(self):
        return self.cfg.setdefault("buttons", {})

    def mapping_for(self, idx):
        return self.mappings.get(str(idx)) or {
            "action": "none", "mode": "tap", "hz": 20, "key": ""}

    def _rapid_hz(self, m):
        try:
            hz = float(m.get("hz") or self.cfg.get("rapid_hz", 20.0))
        except (TypeError, ValueError):
            hz = 20.0
        return max(0.5, min(hz, MAX_RAPID_HZ))

    def _rapid_delay(self, m):
        """连发「启动延迟」(秒)：用来区分「点一下」和「按住」。

        SendInput 注入的按键不会触发 Windows 自动重复，所以"长按连续输入"只能靠连发补发。
        但连发若是按下即开始，一次快速点按（几十毫秒）也会补发 2~3 次
        —— 表现为"只点一下却删了 3 个字母"。
        因此按下后先等 delay 秒（这段只发第一次），超过 delay 才进入连发。
        delay 可用全局 rapid_delay 配置，也能被某一行的 delay 覆盖；
        显式设为 0（或负数）则退化成旧的"按下即连发"。
        """
        try:
            d = m.get("delay")
            if d is None:
                d = self.cfg.get("rapid_delay", RAPID_HOLD_DELAY)
            d = float(d)
        except (TypeError, ValueError):
            d = RAPID_HOLD_DELAY
        if d <= 0:
            return 1.0 / self._rapid_hz(m)
        return min(d, 3.0)

    def _say(self, msg):
        if self.log:
            self.log(msg)

    # ---- 语音输入 ----
    def _voice_hotkey(self):
        spec = self.cfg.get("voice_hotkey") or VOICE_HOTKEY
        return spec if parse_key_spec(spec)[1] is not None else VOICE_HOTKEY

    def _voice_fire(self):
        """发一次语音输入热键。

        加了最小间隔保护：万一有人把语音绑定误设成「连发」，
        也不会把听写面板刷到疯狂开关。
        """
        now = time.perf_counter()
        if now - self._voice_last < VOICE_MIN_INTERVAL:
            return
        self._voice_last = now
        self.sim.combo_tap(self._voice_hotkey())
        self._say("语音输入 %s" % key_spec_display(self._voice_hotkey()))

    # ---- 生命周期 ----
    def start(self):
        self.running = True
        self._last_t = time.perf_counter()

    def stop(self):
        self.running = False
        self._release_all_holds()
        self.sim.release_all()
        self._reset_scroll()

    def _reset_scroll(self):
        self._scroll_acc = 0.0
        self._scroll_smooth = 0.0
        self.scroll_rate = 0.0

    def toggle_enabled(self, value=None):
        self.enabled = (not self.enabled) if value is None else bool(value)
        if not self.enabled:
            self._release_all_holds()
            self.sim.release_all()
            self._rapid_next.clear()
            self._reset_scroll()
        if self.on_toggle:
            self.on_toggle(self.enabled)
        self._say("映射已%s" % ("开启" if self.enabled else "关闭"))
        return self.enabled

    # ---- 主更新 ----
    def update(self, buttons, axes=None, hats=None):
        now = time.perf_counter()
        dt = now - self._last_t
        self._last_t = now
        dt = 0.001 if dt <= 0 else min(dt, 0.5)

        self._check_hotkey()
        if not self.running:
            return

        # 归一化按键编号（兼容 int / str 两种键），并记下「上一帧认识的全部键」。
        #
        # 关键：十字键(100~103)在 poll() 里是 *只在按下时才往 buttons 里塞键*，
        # 松开后那个键直接从字典里消失；普通按钮则是 True/False 都一直存在。
        # 如果只遍历「本帧存在的键」，hat 的下降沿就永远看不到：
        #   tap  模式 -> 只有第一次按生效，之后再按全哑（快进「按一下没反应」的真凶）
        #   hold 模式 -> 松开不释放，等于一直按着
        # 所以这里把「上一帧有、本帧没有」的键补成 False，显式制造释放边沿。
        cur = {}
        for k, v in (buttons or {}).items():
            try:
                cur[int(k)] = bool(v)
            except (TypeError, ValueError):
                continue
        ids = set(cur.keys()) | set(self._btn_prev.keys())

        if self.enabled:
            for idx in ids:
                self._handle_button(idx, cur.get(idx, False), now)
            self._handle_mouse_axes(axes or [], dt)
        else:
            for idx in ids:
                if self._btn_prev.get(idx):
                    self._release_button(idx, now)
                if (cur.get(idx, False) and not self._btn_prev.get(idx, False)
                        and self.mapping_for(idx).get("action") == "toggle"):
                    self.toggle_enabled()
        for idx in ids:
            self._btn_prev[idx] = cur.get(idx, False)

    # ---- 热键 ----
    def _check_hotkey(self):
        if not IS_WINDOWS:
            return
        hk = self.cfg.get("hotkey") or {}
        if not hk.get("enabled", True):
            return
        vk = key_to_vk(hk.get("key", "f12"))
        if vk is None:
            return
        pressed = bool(_GetAsyncKeyState(vk) & 0x8000)
        if hk.get("ctrl", True):
            pressed = pressed and bool(_GetAsyncKeyState(VK_TABLE["ctrl"]) & 0x8000)
        if pressed and not self._hotkey_prev:
            self.toggle_enabled()
        self._hotkey_prev = pressed

    # ---- 按钮 ----
    def _handle_button(self, idx, cur, now):
        prev = self._btn_prev.get(idx, False)
        m = self.mapping_for(idx)
        action = m.get("action", "none")
        mode = m.get("mode", "tap")
        if cur and not prev:
            self._on_press(idx, m, action, mode, now)
        if prev and not cur:
            self._on_release(idx, m, action, mode)
        if cur and mode == "rapid":
            interval = 1.0 / self._rapid_hz(m)
            nxt = self._rapid_next.get(idx)
            if nxt is None:
                nxt = now
            budget = 0
            while now >= nxt and budget < 8:
                self._fire(action, m)
                nxt += interval
                budget += 1
            self._rapid_next[idx] = nxt
        elif not cur:
            self._rapid_next.pop(idx, None)

    def _on_press(self, idx, m, action, mode, now):
        if action == "none":
            return
        if action == "toggle":
            self.toggle_enabled()
            return
        if mode == "tap":
            self._fire(action, m)
        elif mode == "hold":
            self._press_hold(action, m)
            self._down_state[idx] = True
        elif mode == "rapid":
            # 按下立刻发一次，然后**先等「启动延迟」再进入连发**：
            #   点一下(短于 delay)  -> 只发一次（不会一点就删 3 个）
            #   按住(超过 delay)    -> 之后按 hz 连续触发
            # 顺带避开旧的"第一帧双发"问题：只要 delay>0，本帧末尾的连发结算
            # 就不会满足 now>=next，自然不会再补发一次。
            self._rapid_next[idx] = now + self._rapid_delay(m)
            self._fire(action, m)

    def _on_release(self, idx, m, action, mode):
        if mode == "hold" and self._down_state.pop(idx, False):
            self._release_hold(action, m)

    def _release_all_holds(self):
        for idx in list(self._down_state.keys()):
            m = self.mapping_for(idx)
            self._release_hold(m.get("action", "none"), m)
        self._down_state.clear()

    def _release_button(self, idx, now=None):
        m = self.mapping_for(idx)
        if self._down_state.pop(idx, False):
            self._release_hold(m.get("action", "none"), m)
        self._rapid_next.pop(idx, None)
        if now is not None:
            self._btn_prev[idx] = False

    def _press_hold(self, action, m):
        if action in ("mouse_left", "mouse_right", "mouse_middle"):
            self.sim.mouse_down(action.split("_", 1)[1])
        elif action == "key":
            self.sim.key_down(key_to_vk(m.get("key")))
        elif action == "voice":
            # 「按住不放」= 按住说话：按下时开，松开时关
            self._voice_fire()

    def _release_hold(self, action, m):
        if action in ("mouse_left", "mouse_right", "mouse_middle"):
            self.sim.mouse_up(action.split("_", 1)[1])
        elif action == "key":
            self.sim.key_up(key_to_vk(m.get("key")))
        elif action == "voice":
            self._voice_last = 0.0        # 松开时不受最小间隔限制
            self._voice_fire()

    def _fire(self, action, m):
        if action == "mouse_left":
            self.sim.click("left")
        elif action == "mouse_right":
            self.sim.click("right")
        elif action == "mouse_middle":
            self.sim.click("middle")
        elif action == "mouse_double":
            self.sim.double_click("left", float(self.cfg.get("double_click_gap", 0.04)))
        elif action == "wheel_up":
            self.sim.scroll(1)
        elif action == "wheel_down":
            self.sim.scroll(-1)
        elif action == "key":
            self.sim.key_tap(key_to_vk(m.get("key")))
        elif action == "key_combo":
            self.sim.combo_tap(m.get("key"))
        elif action == "voice":
            self._voice_fire()

    # ---- 摇杆 ----
    def _move_axes(self, axes, dt, sens, dead, expo, invert_y, ix, iy):
        """把 (ix, iy) 两根轴按灵敏度/死区/曲线换算成鼠标位移。"""
        try:
            sens = float(sens)
            dead = min(max(float(dead), 0.0), 0.9)
            expo = max(float(expo), 1.0)
        except (TypeError, ValueError):
            sens, dead, expo = 1400.0, 0.18, 1.6
        if sens <= 0.0:
            return

        def axis(i):
            try:
                v = float(axes[i]) if i < len(axes) else 0.0
            except (TypeError, ValueError):
                return 0.0
            return 0.0 if v != v else v          # NaN 保护

        def curve(v):
            a = abs(v)
            if a <= dead:
                return 0.0
            n = min((a - dead) / (1.0 - dead), 1.0) ** expo
            return n if v > 0 else -n

        dx = curve(axis(ix))
        dy = curve(axis(iy))
        if invert_y:
            dy = -dy
        if dx or dy:
            self.sim.move(dx * sens * dt, dy * sens * dt)

    def _handle_mouse_axes(self, axes, dt):
        mm = self.cfg.get("mouse") or {}
        self._handle_scroll_axes(axes, dt, mm)       # 滚轮（右摇杆滚轮旧功能，默认已关）
        if len(axes) < 2:
            return

        stick = mm.get("stick", "left")
        if stick == "none":
            return                                    # 明确关掉「摇杆当鼠标」

        rcfg = mm.get("right")
        if not isinstance(rcfg, dict):
            rcfg = {}
        right_mouse = bool(rcfg.get("mouse"))

        # 左摇杆（主鼠标，快）
        if stick in ("left", "both") or (stick == "right" and not right_mouse):
            self._move_axes(axes, dt, mm.get("sensitivity", 1400.0),
                            mm.get("deadzone", 0.18), mm.get("exponent", 1.6),
                            bool(mm.get("invert_y")), 0, 1)

        # 右摇杆（默认低灵敏度，精调）
        if right_mouse:
            self._move_axes(axes, dt, rcfg.get("sensitivity", 500.0),
                            rcfg.get("deadzone", 0.18), rcfg.get("exponent", 1.8),
                            bool(rcfg.get("invert_y")), 2, 3)
        elif stick in ("right", "both"):
            self._move_axes(axes, dt, mm.get("sensitivity", 1400.0),
                            mm.get("deadzone", 0.18), mm.get("exponent", 1.6),
                            bool(mm.get("invert_y")), 2, 3)

    # ---- 右摇杆当滚轮(缓慢滚动)----
    def _handle_scroll_axes(self, axes, dt, mm=None):
        """把某根摇杆轴映射成滚轮。

        速度是「格/秒」：满推 = scroll.speed 格每秒，松手立刻停。
        曲线 = 线性段 + 指数段混合，轻推极慢(方便逐行微调)，越推越快。
        一阶低通平滑 + 单帧限幅，避免摇杆抖动导致滚动跳来跳去。
        """
        if mm is None:
            mm = self.cfg.get("mouse") or {}
        if not mm.get("right_stick_scroll"):
            self._reset_scroll()
            return

        sc = mm.get("scroll")
        if not isinstance(sc, dict):
            sc = {}

        def num(key, default, lo, hi):
            try:
                v = float(sc.get(key, default))
            except (TypeError, ValueError):
                v = default
            return min(max(v, lo), hi)

        try:
            ai = int(sc.get("axis", 3))
        except (TypeError, ValueError):
            ai = 3

        speed = num("speed", 6.0, 0.0, 60.0)
        dead = num("deadzone", 0.22, 0.0, 0.9)
        expo = num("exponent", 1.9, 1.0, 6.0)
        smooth = num("smooth", 0.25, 0.0, 0.95)
        mix = num("linear_mix", 0.30, 0.0, 1.0)
        limit = int(num("limit", 4, 1, 60))

        try:
            v = float(axes[ai]) if ai < len(axes) else 0.0
        except (TypeError, ValueError):
            v = 0.0
        if v != v:      # NaN 保护
            v = 0.0

        a = abs(v)
        if a <= dead or speed <= 0.0:
            # 回到死区：快速收尾，不留长拖尾
            self._scroll_smooth *= 0.35
            if abs(self._scroll_smooth) < 0.25:
                self._scroll_smooth = 0.0
        else:
            t = min((a - dead) / (1.0 - dead), 1.0)
            mag = mix * t + (1.0 - mix) * (t ** expo)
            # SDL 的 Y 轴：向上推为负值；notches 正值 = 向上滚
            direction = 1.0 if v < 0 else -1.0
            if sc.get("invert"):
                direction = -direction
            target = mag * direction * speed
            self._scroll_smooth += (target - self._scroll_smooth) * (1.0 - smooth)

        self.scroll_rate = self._scroll_smooth

        # 反向立刻清掉残留，避免"想往下滚却先往上跳一格"
        if self._scroll_acc and (self._scroll_acc > 0) != (self._scroll_smooth > 0):
            self._scroll_acc = 0.0

        self._scroll_acc += self._scroll_smooth * dt
        steps = int(self._scroll_acc)          # 向零截断
        if steps > limit:
            steps = limit
        elif steps < -limit:
            steps = -limit
        if steps:
            self.sim.scroll(steps)
            self._scroll_acc -= steps


# --- 系统层设备重置 ---------------------------------------------------------
# 手柄待机/睡死之后，Windows 里的设备节点可能卡住：SDL 枚举不到、XInput 也看不见，
# 这时程序怎么重建都没用（重启软件也一样）。唯一的办法是让系统把手柄设备
# 重新加载一次 —— 等价于拔下来再插上去。这一步需要管理员权限，所以用 UAC 提权。
DEVICE_RESET_PS = r'''$ErrorActionPreference = "SilentlyContinue"
$names = "XBOX|Xbox|手柄|Controller|\u6e38\u620f\u63a7\u5236\u5668"
$devs = @()
$devs += @(Get-PnpDevice -PresentOnly -Class XnaComposite)
$devs += @(Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq "HIDClass" -and $_.FriendlyName -match $names })
$devs = @($devs | Sort-Object InstanceId -Unique)
if ($devs.Count -eq 0) { Write-Host "NODEV"; exit 1 }
foreach ($d in $devs) {
  Write-Host ("reset " + $d.InstanceId)
  pnputil /restart-device "$($d.InstanceId)" | Out-Null
}
Start-Sleep -Milliseconds 1200
Write-Host "DONE"
'''


def restart_gamepad_device():
    """请求 Windows 重启手柄设备节点（需要管理员 → 会弹一次 UAC）。

    返回 (ok, 给用户看的提示语)。
    """
    if os.name != "nt":
        return False, "重置手柄驱动仅支持 Windows"
    try:
        import subprocess
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".ps1", prefix="gm_devreset_")
        os.close(fd)
        # 带 BOM 写出，避免 PowerShell 5.1 把中文读成乱码
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write(DEVICE_RESET_PS)
        inner = ("Start-Process -FilePath powershell -Verb RunAs -Wait "
                 "-WindowStyle Hidden -ArgumentList '-NoProfile',"
                 "'-ExecutionPolicy','Bypass','-File','%s'" % path)
        subprocess.run(["powershell", "-NoProfile", "-Command", inner],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True, "已请管理员重启手柄设备（若没反应，请确认 UAC 弹窗已允许）"
    except Exception as exc:
        return False, "重置手柄驱动失败：%s" % exc


# ============================================================================
# 7. 运行时状态（主循环 <-> Web 控制台 共享）
# ============================================================================

class Runtime(object):
    def __init__(self, cfg):
        import threading
        self.lock = threading.RLock()
        self.quit = False
        self.cfg = cfg
        self.pad = Gamepad()
        self.engine = Engine(cfg)
        self.device = {"name": "", "connected": False,
                       "nbuttons": 0, "naxes": 0, "nhats": 0, "index": 0,
                       "stale": False, "recovers": 0, "xinput": False}
        self.devices = []
        self.pressed = []
        self.axes = []
        self.hats = []
        self.error = ""
        self.pad_note = ""       # 手柄自愈过程中的提示（假连接 / 重连中）
        self.dirty_rows = set()
        import queue
        self.cmds = queue.Queue()

    def publish(self):
        pad = self.pad
        with self.lock:
            self.devices = list(pad.names)
            self.device = {"name": pad.name, "connected": pad.connected,
                           "nbuttons": pad.nbuttons, "naxes": pad.naxes,
                           "nhats": pad.nhats, "index": pad.index,
                           "stale": bool(pad.stale),
                           "recovers": int(pad.recover_count),
                           "xinput": bool(pad.xinput.available)}
            self.pressed = [i for i, v in pad.buttons.items() if v]
            self.axes = [round(float(a), 3) for a in pad.axes]
            self.hats = [list(h) for h in pad.hats]
            self.error = pad.error if not pad.available else ""
            self.pad_note = pad.last_error or ""

    def drain_commands(self):
        while True:
            try:
                cmd = self.cmds.get_nowait()
            except Exception:
                return
            kind = cmd.get("cmd")
            if kind == "quit":
                self.quit = True
            elif kind == "toggle":
                self.engine.toggle_enabled()
            elif kind == "set_enabled":
                self.engine.toggle_enabled(bool(cmd.get("value")))
            elif kind == "rescan":
                self.pad.rescan()
            elif kind == "resetpad":
                # 「重连手柄」：把 SDL 手柄子系统整个重建并重新打开
                self.pad.deep_reset()
                self.dirty_rows.add("all")
            elif kind == "resetdevice":
                # 「重置手柄驱动」：让 Windows 重启设备节点（等价于拔插一次），
                # 会弹一次 UAC；这一步只救"系统层卡死"的情况
                ok, msg = restart_gamepad_device()
                self.pad.last_error = msg
                if ok:
                    self.pad.deep_reset()
                self.dirty_rows.add("all")
            elif kind == "open":
                self.pad.open(int(cmd.get("index", 0)))
                self.dirty_rows.add("all")
            elif kind == "save":
                save_config(self.cfg)
            elif kind == "config":
                with self.lock:
                    _deep_merge(self.cfg, cmd.get("value") or {})
                    self.cfg.pop("_scroll_acc", None)
                    self.engine.enabled = bool(self.cfg.get("enabled", True))
                    self.engine.cfg = self.cfg
            elif kind == "rows":
                rows = cmd.get("value") or {}
                with self.lock:
                    btns = self.cfg.setdefault("buttons", {})
                    for k, v in rows.items():
                        k = str(k)
                        cur = btns.get(k)
                        # 面板只发「被改动的字段」(dirty)，所以这里必须**合并**而不是整行替换。
                        # 曾经写成 btns[k] = v：在面板里只改一下「频率」那一格，就会把
                        # 同一行的 action / key / mode 全抹掉，十字键直接失效（真出过事故）。
                        if isinstance(v, dict) and isinstance(cur, dict):
                            cur.update(v)
                        else:
                            btns[k] = v
                    self.cfg.pop("_scroll_acc", None)
                    save_config(self.cfg)
            elif kind == "clear_rows":
                with self.lock:
                    self.cfg["buttons"] = {}
                    self.dirty_rows.add("all")
            elif kind == "reset":
                with self.lock:
                    d = default_config()
                    self.cfg.clear()
                    self.cfg.update(d)
                    self.engine.enabled = bool(self.cfg.get("enabled", True))
                    self.engine.cfg = self.cfg
                    self.dirty_rows.add("all")

    def rows_payload(self):
        pad = self.pad
        ids = pad.all_button_ids()
        for k in list(self.cfg.get("buttons", {}).keys()):
            try:
                ki = int(k)
            except ValueError:
                continue
            if ki not in ids and ki < DPAD_BASE:
                ids.append(ki)
        ids = sorted(set(ids))
        out = []
        for idx in ids:
            m = self.engine.mapping_for(idx)
            out.append({
                "idx": idx,
                "name": pad.button_name(idx),
                "action": m.get("action", "none"),
                "mode": m.get("mode", "tap"),
                "key": m.get("key", "") or "",
                "hz": m.get("hz", self.cfg.get("rapid_hz", 20)),
            })
        return out


# ============================================================================
# 8. Web 控制台
# ============================================================================

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gamepad Mapper · 手柄当无线键盘</title>
<style>
:root{
  --bg:#f4f5f7; --card:#ffffff; --fg:#1f2329; --sub:#6b7280; --line:#e5e7eb;
  --accent:#2563eb; --ok:#16a34a; --bad:#dc2626; --warn:#d97706;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:14px/1.6 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line);
  padding:14px 22px;display:flex;align-items:center;gap:14px;
  position:sticky;top:0;z-index:10}
h1{font-size:17px;margin:0;font-weight:700;letter-spacing:.3px}
h1 span{color:var(--sub);font-weight:400;font-size:12px;margin-left:8px}
.pill{margin-left:auto;padding:5px 14px;border-radius:999px;font-size:12.5px;
  font-weight:700;color:#fff;cursor:pointer;user-select:none;border:none}
.pill.on{background:var(--ok)} .pill.off{background:var(--bad)}
main{display:grid;grid-template-columns:318px 1fr;gap:16px;padding:16px 22px 40px;
  align-items:start;max-width:1500px;margin:0 auto}
@media(max-width:1000px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}
.card h2{font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:var(--sub);
  margin:0 0 10px;font-weight:700}
.dev{font-weight:600;font-size:13.5px;word-break:break-all}
.meta{color:var(--sub);font-size:12px;margin-top:3px}
.live{font-family:Consolas,monospace;font-size:12px;color:var(--sub);
  background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:8px 10px;
  margin-top:9px;min-height:42px;white-space:pre-wrap;word-break:break-all}
.row{display:flex;align-items:center;gap:8px;margin:9px 0}
.row label{width:96px;color:var(--sub);font-size:12.5px;flex:none}
.sub{font-weight:600;font-size:12.5px;color:var(--accent);margin:12px 0 2px}
input[type=range]{flex:1;accent-color:var(--accent)}
select,input[type=text],input[type=number]{border:1px solid var(--line);border-radius:7px;
  padding:5px 8px;font:inherit;font-size:13px;background:#fff;color:var(--fg);outline:none}
select:focus,input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
button{font:inherit;font-size:13px;padding:6px 13px;border-radius:8px;
  border:1px solid var(--line);background:#fff;cursor:pointer;transition:.15s}
button:hover{border-color:#c9ced6;background:#fafbfc}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button.primary:hover{background:#1d4ed8}
button.danger{color:var(--bad);border-color:#fecaca}
.val{width:56px;text-align:right;color:var(--sub);font-size:12px;flex:none}
table{width:100%;border-collapse:collapse}
th,td{padding:6px 8px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}
th{color:var(--sub);font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;
  font-weight:700;position:sticky;top:57px;background:var(--card);z-index:2}
tbody tr.hit{background:#dcfce7}
tbody tr.hit td{color:#14532d}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:#d1d5db;margin-right:8px;vertical-align:middle}
tbody tr.hit .dot{background:var(--ok);box-shadow:0 0 0 3px rgba(22,163,74,.2)}
td.tight{padding:4px 6px}
.kbox{font-family:Consolas,monospace;font-size:12px;text-align:center;cursor:pointer;
  background:#f8fafc;border:1px dashed #cbd5e1;border-radius:6px;padding:4px 6px;min-width:64px;
  display:inline-block;color:var(--sub)}
.kbox.learning{border-color:var(--accent);color:var(--accent);border-style:solid}
.kbox.set{background:#eff6ff;border-color:#93c5fd;color:#1d4ed8;border-style:solid}
.tools{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.hint{color:var(--sub);font-size:12px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);
  background:#111827;color:#fff;padding:9px 18px;border-radius:9px;font-size:13px;
  opacity:0;transition:.25s;pointer-events:none;z-index:99}
.toast.show{opacity:1}
.warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:9px;
  padding:9px 12px;font-size:12.5px;margin-bottom:12px}
</style>
</head>
<body>
<header>
  <h1>Gamepad Mapper<span>手柄 → 无线键盘 / 鼠标</span></h1>
  <button id="pill" class="pill on">运行中</button>
</header>
<main>
  <div>
    <div class="card">
      <h2>手柄设备</h2>
      <div class="dev" id="devname">检测中…</div>
      <div class="meta" id="devmeta"></div>
      <div id="devwarn" class="warn" style="display:none;margin-top:10px"></div>
      <div class="row" style="margin-top:10px">
        <select id="devsel" style="flex:1"></select>
        <button onclick="post('rescan',{})">重新扫描</button>
      </div>
      <div class="row">
        <button onclick="post('resetpad',{})">重连手柄</button>
        <button class="danger" onclick="resetDevice()">重置手柄驱动…</button>
      </div>
      <div class="hint">待机 / 睡眠唤醒后手柄没反应时：先点「重连手柄」；
        还不行再点「重置手柄驱动…」（会弹 UAC，需管理员，相当于拔插一次手柄）。</div>
      <div class="live" id="live">按下手柄按钮以查看实时状态</div>
    </div>

    <div class="card">
      <h2>总开关</h2>
      <label class="row"><input type="checkbox" id="cbHotkey"> 启用 Ctrl+F12 全局热键</label>
      <div class="hint">任何时候按 Ctrl+F12 都能临时关掉/开启映射，避免影响打字。</div>
    </div>

    <div class="card">
      <h2>摇杆当鼠标</h2>
      <div class="row"><label>使用摇杆</label>
        <select id="stick">
          <option value="left">左摇杆</option>
          <option value="right">右摇杆</option>
          <option value="both">两个都</option>
          <option value="none">不启用</option>
        </select></div>

      <div class="sub">左摇杆（快，主力）</div>
      <div class="row"><label>左摇杆灵敏度</label><input type="range" id="sens" min="100" max="4000" step="50"><span class="val" id="sensv"></span></div>
      <div class="row"><label>左摇杆死区</label><input type="range" id="dead" min="0" max="0.6" step="0.01"><span class="val" id="deadv"></span></div>
      <label class="row"><input type="checkbox" id="invy"> 左摇杆反转 Y 轴（上下颠倒时勾选）</label>

      <hr style="border:none;border-top:1px solid var(--line);margin:10px 0">

      <div class="sub">右摇杆（慢，精调）</div>
      <label class="row"><input type="checkbox" id="rmouse"> 右摇杆也控制鼠标</label>
      <div class="row"><label>右摇杆灵敏度</label><input type="range" id="rsens" min="50" max="2000" step="10"><span class="val" id="rsensv"></span></div>
      <div class="row"><label>右摇杆死区</label><input type="range" id="rdead" min="0" max="0.6" step="0.01"><span class="val" id="rdeadv"></span></div>
      <label class="row"><input type="checkbox" id="rinvy"> 右摇杆反转 Y 轴</label>

      <div class="hint">左右摇杆灵敏度<b>各自独立、互不影响</b>：左摇杆管快速移动，右摇杆管精细瞄准。
        默认左 <b>1400</b> / 右 <b>500</b>，想调谁就拖谁。</div>
    </div>

    <div class="card">
      <h2>右摇杆当滚轮（缓慢滚动）</h2>
      <label class="row"><input type="checkbox" id="rss"> 启用：推右摇杆上下 = 滚轮</label>
      <div class="hint">现在<b>默认关闭</b>：滚轮交给十字键 ↑↓，右摇杆让给了「低灵敏度移动鼠标」。
        想换回来就勾上这里（会和上面「右摇杆控制鼠标」自动二选一）。</div>
      <div class="hint">轻推极慢（方便逐行看），推到底变快；松手立刻停。满推默认 <b>6 格/秒</b>，属于慢速。</div>
      <div class="row"><label>满推速度</label><input type="range" id="scspd" min="1" max="30" step="0.5"><span class="val" id="scspdv"></span></div>
      <div class="row"><label>死区</label><input type="range" id="scdead" min="0.05" max="0.6" step="0.01"><span class="val" id="scdeadv"></span></div>
      <div class="row"><label>加速曲线</label><input type="range" id="scexp" min="1" max="4" step="0.1"><span class="val" id="scexpv"></span></div>
      <div class="row"><label>平滑度</label><input type="range" id="scsm" min="0" max="0.7" step="0.05"><span class="val" id="scsmv"></span></div>
      <label class="row"><input type="checkbox" id="scinv"> 反向（向上推 = 向下滚）</label>
      <label class="row"><input type="checkbox" id="scsmooth"> 柔和模式（一键设成极缓慢）</label>
      <div class="hint" id="sclive">当前滚动速率：0.00 格/秒</div>
    </div>

    <div class="card">
      <h2>连点 / 连发</h2>
      <div class="row"><label>默认频率</label><input type="range" id="hz" min="1" max="100" step="1"><span class="val" id="hzv"></span></div>
      <div class="row"><label>长按启动延迟</label><input type="range" id="rdel" min="0" max="1000" step="20"><span class="val" id="rdelv"></span></div>
      <div class="row"><label>双击间隔</label><input type="range" id="gap" min="10" max="200" step="5"><span class="val" id="gapv"></span></div>
      <div class="hint">「连发」= 按住不放时按该频率无限触发。范围 <b>0.5~100</b> 次/秒，可以填小数（如 1.2 = 每 0.83 秒一次）。<br>
        <b>长按启动延迟</b>：按下后先等这么久才开始连发 —— 在延迟内松手只触发 <b>1 次</b>（点一下 = 按一下），
        按住超过延迟才连续触发。觉得「点一下却触发好几次（如删了 3 个字）」就把它<b>调大</b>；
        嫌长按起动慢就调小；<b>0</b> = 按下立刻开始连发（旧行为）。</div>
    </div>

    <div class="card">
      <h2>语音输入</h2>
      <div class="row"><label>触发的组合键</label>
        <input type="text" id="voicekey" placeholder="win+h" style="width:160px"></div>
      <div class="hint">默认 <b>Win+H</b>（Windows 自带的语音输入 / 听写）。
        当前已绑在 <b>开始(Start)</b> 键上：在能打字的地方按一下就说，再按一下结束；
        把该键的「触发方式」改成<b>按住不放</b>，就变成「按住说、松开停」。
        想换键就在映射表里把那个手柄键的动作选成<b>语音输入</b>。</div>
      <div class="row" style="margin:8px 0 0;gap:8px;flex-wrap:wrap">
        <button onclick="setVoice('win+h')">用 Win+H 语音输入</button>
        <button onclick="setVoice('win+ctrl+s')">用 Win+Ctrl+S 语音访问</button>
      </div>
      <div class="hint">Win11 的「语音访问」要先在 设置 → 辅助功能 → 语音 里打开一次。<br>
        组合键想换成别的（例如 <code>ctrl+shift+v</code>）直接改上面的输入框，或去映射表里
        把某个键的动作选成<b>组合键</b>后直接按键盘学习。</div>
    </div>

    <div class="card">
      <div class="row" style="margin:0">
        <button class="primary" onclick="post('save',{})">保存配置</button>
        <button onclick="post('reset',{})">恢复默认</button>
        <button class="danger" onclick="post('quit',{})">退出程序</button>
      </div>
      <div class="meta" id="stat"></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:0">
    <h2>按键映射表</h2>
    <div id="warnbox"></div>
    <div class="tools">
      <button onclick="cycleAll('mode')">批量切换触发方式</button>
      <button onclick="clearRows()">清空全部</button>
      <span class="hint">点「按键」格子 → 直接按键盘上的键即可学习绑定</span>
    </div>
    <div class="hint" style="margin:-2px 0 8px">
      十字键 ← → 是快退 / 快进：<b>按一下发一次方向键</b>（播放器一次约 +5 秒），
      按住不放不会连续快进。想改成「按住连续快进」，把那一行的触发方式换成「连发」。
    </div>
    <table>
      <thead><tr>
        <th style="width:170px">手柄按钮</th><th style="width:130px">动作</th>
        <th style="width:120px">键盘按键</th><th style="width:150px">触发方式</th><th style="width:100px">频率 Hz</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>
<div class="toast" id="toast"></div>
<script>
const ACTIONS = __ACTIONS__, MODES = __MODES__;
let STATE = null, ROWS = [], learning = null, lastDev = -1, dirty = {};

function toast(m){const t=document.getElementById('toast');t.textContent=m;
  t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('show'),1600);}

function post(cmd, extra){
  fetch('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(Object.assign({cmd:cmd},extra))}).catch(()=>{});
}

/* 重置手柄驱动：让 Windows 重启设备节点（需要管理员，会弹 UAC） */
function resetDevice(){
  if(!confirm('将请求管理员权限，重启 Windows 里的手柄设备（相当于拔下来再插上）。\n\n只在「重连手柄」也救不回来时才需要。\n\n继续？')) return;
  post('resetdevice',{});
  toast('已请求重置手柄驱动，请在 UAC 弹窗中允许');
}

/* ---------- 表格 ---------- */
function buildTable(rows){
  ROWS = rows;
  const tb = document.getElementById('tbody');
  tb.innerHTML = '';
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    tr.id = 'r'+r.idx;
    tr.dataset.idx = r.idx;
    tr.innerHTML =
      '<td><span class="dot"></span>'+esc(r.name)+'</td>'+
      '<td class="tight">'+sel('act',r.idx,r.action,ACTIONS)+'</td>'+
      '<td class="tight"><span class="kbox'+(r.key?' set':'')+'" id="k'+r.idx+'" data-idx="'+r.idx+'">'+
        (r.key?esc(r.key):'未绑定')+'</span></td>'+
      '<td class="tight">'+sel('mode',r.idx,r.mode,MODES)+'</td>'+
      '<td class="tight"><input type="number" min="0.5" max="100" step="0.1" value="'+r.hz+'" data-idx="'+r.idx+
        '" data-f="hz" style="width:74px"></td>';
    tb.appendChild(tr);
  });
  tb.querySelectorAll('select').forEach(s=>s.addEventListener('change',onField));
  tb.querySelectorAll('input[type=number]').forEach(s=>s.addEventListener('change',onField));
  tb.querySelectorAll('.kbox').forEach(k=>k.addEventListener('click',startLearn));
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function sel(field,idx,val,list){
  let h = '<select data-idx="'+idx+'" data-f="'+field+'">';
  for(const [label,id] of list)
    h += '<option value="'+id+'"'+(id===val?' selected':'')+'>'+label+'</option>';
  return h+'</select>';
}
function onField(e){
  const el = e.target, idx = el.dataset.idx, f = el.dataset.f;
  let v = el.value;
  if(f==='hz'){ v = Math.max(0.5,Math.min(100, parseFloat(v)||20)); el.value = v; }
  dirty[idx] = dirty[idx] || {};
  dirty[idx][f] = v;
  if(f==='act' && v==='key'){ setTimeout(()=>startLearn({target:document.getElementById('k'+idx)}),0); }
  flush(idx);
}
function flush(idx){
  if(!dirty[idx]) return;
  post('rows',{value:{[idx]:dirty[idx]}});
  delete dirty[idx];
}
function cycleAll(field){
  const list = field==='mode' ? MODES : ACTIONS;
  const ids = list.map(x=>x[1]);
  ROWS.forEach(r=>{
    const el = document.querySelector('select[data-idx="'+r.idx+'"][data-f="'+field+'"]');
    const next = ids[(ids.indexOf(el.value)+1)%ids.length];
    el.value = next; dirty[r.idx]={[field]:next};
  });
  ROWS.forEach(r=>flush(r.idx));
  toast('已批量切换');
}
function clearRows(){ if(!confirm('清空所有按键映射？')) return; post('clear_rows',{}); }

/* ---------- 按键学习 ---------- */
const CODEMAP = {Space:'space',Enter:'enter',Escape:'esc',Backspace:'backspace',Tab:'tab',
  ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',
  ShiftLeft:'shift',ShiftRight:'rshift',ControlLeft:'ctrl',ControlRight:'rctrl',
  AltLeft:'alt',AltRight:'ralt',MetaLeft:'lwin',MetaRight:'rwin',
  CapsLock:'capslock',Insert:'insert',Delete:'delete',Home:'home',End:'end',
  PageUp:'pageup',PageDown:'pagedown',PrintScreen:'printscreen',
  Minus:'-',Equal:'=',BracketLeft:'[',BracketRight:']',Backslash:'\\',
  Semicolon:';',Quote:"'",Comma:',',Period:'.',Slash:'/',Backquote:'`',
  NumpadAdd:'add',NumpadSubtract:'subtract',NumpadMultiply:'multiply',
  NumpadDivide:'divide',NumpadDecimal:'decimal'};
function codeToKey(code,key){
  if(CODEMAP[code]) return CODEMAP[code];
  if(/^Key[A-Z]$/.test(code)) return code.slice(3).toLowerCase();
  if(/^Digit[0-9]$/.test(code)) return code.slice(5);
  if(/^Numpad[0-9]$/.test(code)) return 'numpad'+code.slice(6);
  if(/^F([1-9]|1[0-9]|2[0-4])$/.test(code)) return code.toLowerCase();
  if(key && key.length===1) return key.toLowerCase();
  return '';
}
function startLearn(e){
  const el = e.target || e;
  if(!el || !el.dataset) return;
  document.querySelectorAll('.kbox.learning').forEach(k=>k.classList.remove('learning'));
  el.classList.add('learning');
  el.textContent = '按下键盘…';
  learning = el;
}
document.addEventListener('keydown', ev=>{
  if(!learning) return;
  ev.preventDefault(); ev.stopPropagation();
  const idx = learning.dataset.idx;
  const bare = !ev.ctrlKey && !ev.altKey && !ev.shiftKey && !ev.metaKey;
  // 只按下修饰键时不结束学习，继续等真正的主键
  if(bare && ['ControlLeft','ControlRight','ShiftLeft','ShiftRight',
              'AltLeft','AltRight','MetaLeft','MetaRight'].indexOf(ev.code)>=0) return;
  let name = '';
  if(bare && (ev.code==='Escape'||ev.code==='Backspace'||ev.code==='Delete')){
    name = '';                                    // 单独按这些 = 取消绑定
  }else{
    const mods = [];
    if(ev.metaKey) mods.push('win');
    if(ev.ctrlKey) mods.push('ctrl');
    if(ev.altKey)  mods.push('alt');
    if(ev.shiftKey) mods.push('shift');
    name = mods.concat([codeToKey(ev.code, ev.key)]).join('+');
  }
  if(!name){ learning.textContent = ROWS.find(r=>String(r.idx)===idx).key || '未绑定';
    learning.classList.remove('learning'); learning = null; return; }
  learning.textContent = name; learning.classList.add('set');
  learning.classList.remove('learning'); learning = null;
  dirty[idx] = Object.assign(dirty[idx]||{}, {key:name});
  flush(idx);
  toast('已绑定: '+name);
}, true);

function setVoice(spec){
  document.getElementById('voicekey').value = spec;
  post('config',{value:{voice_hotkey: spec}});
  toast('语音输入组合键已设为 '+spec);
}

/* ---------- 状态轮询 ---------- */
function fmt(v,n){return (v===undefined||v===null)?'':Number(v).toFixed(n===undefined?0:n);}
async function tick(){
  try{
    const s = await (await fetch('/api/state')).json();
    STATE = s;
    if(s.error){ document.getElementById('warnbox').innerHTML = '<div class="warn">'+esc(s.error)+'</div>'; }
    else document.getElementById('warnbox').innerHTML = '';

    // 设备
    const dev = s.device, wbox = document.getElementById('devwarn');
    if(dev.connected){
      document.getElementById('devname').textContent =
        (dev.stale ? '◐ ' : '● ') + dev.name;
      document.getElementById('devmeta').textContent =
        '按钮 '+dev.nbuttons+' · 摇杆 '+dev.naxes+' · 十字键 '+dev.nhats
        + (dev.recovers ? ' · 已自愈 '+dev.recovers+' 次' : '');
    }else{
      document.getElementById('devname').textContent = '○ 未检测到手柄';
      document.getElementById('devmeta').textContent = '插上手柄后点「重新扫描」';
    }
    if(dev.connected && dev.stale){
      wbox.style.display = '';
      wbox.innerHTML = '<b>手柄「假连接」</b>：系统里还挂着设备，但收不到任何输入，程序正在自动重连…'
        + (s.pad_note ? '<br>'+esc(s.pad_note) : '')
        + '<br>若一直不恢复：点「重置手柄驱动…」；或把手柄拔下重插 / 按一下 Xbox 键唤醒。';
    }else{
      wbox.style.display = 'none';
    }
    const ds = document.getElementById('devsel');
    if(s.devices.join('|') !== ds.dataset.sig){
      ds.dataset.sig = s.devices.join('|');
      ds.innerHTML = s.devices.map((n,i)=>'<option value="'+i+'">'+esc(n)+'</option>').join('')
        || '<option>（无）</option>';
    }
    ds.value = String(s.device.index);
    if(ds.dataset.bound !== '1'){
      ds.dataset.bound='1';
      ds.addEventListener('change',()=>post('open',{index:parseInt(ds.value)}));
    }

    // 开关
    const pill = document.getElementById('pill');
    pill.textContent = s.enabled ? '运行中' : '已暂停';
    pill.className = 'pill ' + (s.enabled?'on':'off');

    // 实时
    const p = s.pressed || [];
    ROWS.forEach(r=>{
      const tr = document.getElementById('r'+r.idx);
      if(tr) tr.classList.toggle('hit', p.indexOf(r.idx)>=0);
    });
    let txt = p.length ? ('按下: ' + p.map(i=>(ROWS.find(r=>r.idx===i)||{}).name||('#'+i)).join('  '))
                       : '等待输入…';
    if(s.axes && s.axes.length>=4)
      txt += '\n左摇杆('+fmt(s.axes[0],2)+', '+fmt(s.axes[1],2)+')   右摇杆('+fmt(s.axes[2],2)+', '+fmt(s.axes[3],2)+')';
    document.getElementById('live').textContent = txt;
    const sr = Number(s.scroll_rate||0);
    const scEl = document.getElementById('sclive');
    scEl.textContent = '当前滚动速率：' + sr.toFixed(2) + ' 格/秒'
      + (Math.abs(sr) > 0.01 ? (sr > 0 ? '  ↑ 向上' : '  ↓ 向下') : '');
    document.getElementById('stat').textContent =
      '累计点击 '+s.stats.clicks+' 次 · 累计按键 '+s.stats.keys+' 次'
      + (s.stats.scrolls !== undefined ? ' · 累计滚动 '+s.stats.scrolls+' 格' : '');

    // 表格结构变化 -> 重建
    if(s.rows && s.rows.length !== ROWS.length){ rebuild(s.rows); }
    else if(s.rows){ // 同步外部改动（例如恢复默认）
      s.rows.forEach(r=>{
        const cur = ROWS.find(x=>x.idx===r.idx);
        if(!cur) return;
        if(cur.action!==r.action){ setSel(r.idx,'act',r.action); cur.action=r.action; }
        if(cur.mode!==r.mode){ setSel(r.idx,'mode',r.mode); cur.mode=r.mode; }
        if(cur.key!==r.key){ const k=document.getElementById('k'+r.idx);
          if(k){k.textContent=r.key||'未绑定';k.classList.toggle('set',!!r.key);} cur.key=r.key; }
      });
    }
  }catch(e){ /* 服务未就绪 */ }
  setTimeout(tick, 100);
}
function setSel(idx,f,v){ const el=document.querySelector('select[data-idx="'+idx+'"][data-f="'+f+'"]');
  if(el && el.value!==v) el.value=v; }
function rebuild(rows){ const keep=ROWS.map(r=>r.idx).join(',');
  if(rows.map(r=>r.idx).join(',')===keep){ ROWS=rows; return; } buildTable(rows); }

/* ---------- 初始化 ---------- */
function applyCfg(c){
  document.getElementById('cbHotkey').checked = !!(c.hotkey && c.hotkey.enabled);
  document.getElementById('stick').value = (c.mouse&&c.mouse.stick)||'left';
  document.getElementById('invy').checked = !!(c.mouse&&c.mouse.invert_y);
  document.getElementById('rss').checked = !!(c.mouse&&c.mouse.right_stick_scroll);
  setRange('sens','sensv',(c.mouse&&c.mouse.sensitivity)||1400,0);
  setRange('dead','deadv',(c.mouse&&c.mouse.deadzone)||0.18,2);
  const rg = (c.mouse&&c.mouse.right)||{};
  document.getElementById('rmouse').checked = !!rg.mouse;
  setRange('rsens','rsensv', rg.sensitivity!==undefined?rg.sensitivity:500, 0);
  setRange('rdead','rdeadv', rg.deadzone!==undefined?rg.deadzone:0.18, 2);
  document.getElementById('rinvy').checked = !!rg.invert_y;
  setRange('hz','hzv',c.rapid_hz||20,0);
  setRange('rdel','rdelv',(c.rapid_delay!==undefined?c.rapid_delay:0.4)*1000,0,' ms');
  setRange('gap','gapv',(c.double_click_gap||0.04)*1000,0);
  const sc = (c.mouse&&c.mouse.scroll)||{};
  setRange('scspd','scspdv', sc.speed!==undefined?sc.speed:6, 1);
  setRange('scdead','scdeadv', sc.deadzone!==undefined?sc.deadzone:0.22, 2);
  setRange('scexp','scexpv', sc.exponent!==undefined?sc.exponent:1.9, 1);
  setRange('scsm','scsmv', sc.smooth!==undefined?sc.smooth:0.25, 2);
  document.getElementById('scinv').checked = !!sc.invert;
  document.getElementById('voicekey').value = c.voice_hotkey || 'win+h';
}
function setRange(id,vid,v,dec,unit){
  const el=document.getElementById(id); el.value=v;
  document.getElementById(vid).textContent = Number(v).toFixed(dec)
    + (unit!==undefined?unit:(id==='gap'?' ms':(id==='hz'?' Hz':'')));
}
function bindCfg(){
  const push=()=>{
    post('config',{value:{
      enabled: STATE?STATE.enabled:true,
      rapid_hz: parseFloat(document.getElementById('hz').value),
      rapid_delay: parseFloat(document.getElementById('rdel').value)/1000,
      double_click_gap: parseFloat(document.getElementById('gap').value)/1000,
      hotkey:{enabled: document.getElementById('cbHotkey').checked, key:'f12', ctrl:true},
      voice_hotkey: (document.getElementById('voicekey').value||'win+h').trim(),
      mouse:{
        stick: document.getElementById('stick').value,
        sensitivity: parseFloat(document.getElementById('sens').value),
        deadzone: parseFloat(document.getElementById('dead').value),
        invert_y: document.getElementById('invy').checked,
        right_stick_scroll: document.getElementById('rss').checked,
        right:{
          mouse: document.getElementById('rmouse').checked,
          sensitivity: parseFloat(document.getElementById('rsens').value),
          deadzone: parseFloat(document.getElementById('rdead').value),
          invert_y: document.getElementById('rinvy').checked
        },
        scroll:{
          axis: 3,
          speed: parseFloat(document.getElementById('scspd').value),
          deadzone: parseFloat(document.getElementById('scdead').value),
          exponent: parseFloat(document.getElementById('scexp').value),
          linear_mix: 0.30,
          smooth: parseFloat(document.getElementById('scsm').value),
          limit: 4,
          invert: document.getElementById('scinv').checked
        }
      }
    }});
  };
  const live=(id,vid,dec,suffix)=>document.getElementById(id).addEventListener('input',e=>{
    document.getElementById(vid).textContent = Number(e.target.value).toFixed(dec)+(suffix||'');
  });
  live('sens','sensv',0); live('dead','deadv',2); live('hz','hzv',0,' Hz'); live('gap','gapv',0,' ms');
  live('rdel','rdelv',0,' ms');
  live('rsens','rsensv',0); live('rdead','rdeadv',2);
  live('scspd','scspdv',1,' 格/秒'); live('scdead','scdeadv',2);
  live('scexp','scexpv',1); live('scsm','scsmv',2);
  ['sens','dead','hz','gap','cbHotkey','stick','invy','rsens','rdead','rinvy',
   'scspd','scdead','scexp','scsm','scinv','voicekey'].forEach(id=>{
    document.getElementById(id).addEventListener('change',push);
  });
  // 右摇杆只能干一件事：滚轮 或 移动鼠标 —— 互斥，勾一个自动取消另一个
  const exclPair=(a,b)=>document.getElementById(a).addEventListener('change',e=>{
    if(e.target.checked) document.getElementById(b).checked=false;
    push();
  });
  exclPair('rss','rmouse');
  exclPair('rmouse','rss');
  // 柔和模式：一键变成「极缓慢」，适合看文档/网页
  document.getElementById('scsmooth').addEventListener('change',e=>{
    if(!e.target.checked) return;
    const set=(id,v)=>{ document.getElementById(id).value=v; };
    set('scspd',3); set('scdead',0.24); set('scexp',2.2); set('scsm',0.4);
    document.getElementById('rss').checked = true;
    document.getElementById('scinv').checked = false;
    setRange('scspd','scspdv',3,1,' 格/秒');
    setRange('scdead','scdeadv',0.24,2);
    setRange('scexp','scexpv',2.2,1);
    setRange('scsm','scsmv',0.4,2);
    e.target.checked = false;
    push();
    toast('已设为柔和模式（满推 3 格/秒）');
  });
  document.getElementById('pill').addEventListener('click',()=>post('toggle',{}));
}
(async function(){
  const c = await (await fetch('/api/config')).json();
  applyCfg(c);
  const s = await (await fetch('/api/state')).json();
  buildTable(s.rows);
  bindCfg();
  tick();
})();
</script>
</body>
</html>
"""


def build_page():
    return (PAGE
            .replace("__ACTIONS__", json.dumps(ACTION_CHOICES, ensure_ascii=False))
            .replace("__MODES__", json.dumps(MODE_CHOICES, ensure_ascii=False)))


def run_web(rt, port=DEFAULT_PORT, open_browser=True):
    import http.server
    import socketserver
    import threading
    import webbrowser

    page = build_page().encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, page, "text/html; charset=utf-8")
            if path == "/api/ping":
                return self._send(200, '{"app":"gamepad-mapper"}')
            if path == "/api/state":
                with rt.lock:
                    payload = {
                        "enabled": rt.engine.enabled,
                        "device": rt.device,
                        "devices": rt.devices,
                        "pressed": rt.pressed,
                        "axes": rt.axes,
                        "hats": rt.hats,
                        "error": rt.error,
                        "pad_note": rt.pad_note,
                        "rows": rt.rows_payload(),
                        "stats": dict(rt.engine.sim.stats),
                        "scroll_rate": round(rt.engine.scroll_rate, 2),
                    }
                return self._send(200, json.dumps(payload, ensure_ascii=False))
            if path == "/api/config":
                with rt.lock:
                    data = {k: v for k, v in rt.cfg.items() if not k.startswith("_")}
                return self._send(200, json.dumps(data, ensure_ascii=False))
            return self._send(404, "not found")

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b"{}"
                cmd = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                cmd = {}
            rt.cmds.put(cmd)
            return self._send(200, '{"ok":true}')

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = None
    bind_port = port
    for _ in range(20):
        try:
            srv = Server(("127.0.0.1", bind_port), Handler)
            break
        except OSError:
            bind_port += 1
    if srv is None:
        print("[错误] 无法绑定本地端口，请用 --port 指定其它端口")
        return 1

    url = "http://127.0.0.1:%d/" % bind_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("=" * 62)
    print("  %s  控制台已启动" % APP_NAME)
    print("  面板地址: %s" % url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("  界面里点「退出程序」结束；或在本窗口按 Ctrl+C")
    print("=" * 62)

    # ---- 主循环（pygame 必须在主线程轮询）----
    rt.engine.start()
    sup = {"last_input": time.time()}      # 手柄守护用的计时/重试状态
    try:
        while not rt.quit:
            rt.drain_commands()
            rt.pad.poll()
            if pad_input_seen(rt.pad):
                sup["last_input"] = time.time()
            if supervise_pad(rt.pad, sup):
                rt.dirty_rows.add("all")
            rt.engine.update(rt.pad.buttons, rt.pad.axes, rt.pad.hats)
            rt.publish()
            time.sleep(0.004)
    except KeyboardInterrupt:
        pass
    finally:
        rt.engine.stop()
        try:
            save_config(rt.cfg)
            print("配置已保存 -> %s" % CONFIG_PATH)
        except Exception as exc:
            print("[warn] 保存配置失败：%s" % exc)
        srv.shutdown()
        print("已退出。")
    return 0


# ============================================================================
# 9. 无界面模式
# ============================================================================

def run_nogui(cfg):
    pad = Gamepad()
    if not pad.available:
        print("[错误] %s" % pad.error)
        return 2
    if pad.connected:
        print("手柄: %s  (按钮 %d / 摇杆 %d / 十字键 %d)"
              % (pad.name, pad.nbuttons, pad.naxes, pad.nhats))
    else:
        print("未检测到手柄，等待插入… (Ctrl+C 退出)")
    eng = Engine(cfg)
    eng.log = lambda m: print("[%s] %s" % (time.strftime("%H:%M:%S"), m))
    eng.start()
    print("映射运行中。Ctrl+F12 开关映射，Ctrl+C 退出。")
    sup = {"last_input": time.time()}
    try:
        while True:
            pad.poll()
            if pad_input_seen(pad):
                sup["last_input"] = time.time()
            supervise_pad(pad, sup)
            eng.update(pad.buttons, pad.axes, pad.hats)
            time.sleep(0.004)
    except KeyboardInterrupt:
        print("\n退出。")
    finally:
        eng.stop()
    return 0


# ============================================================================
# 10. 入口
# ============================================================================

def check_env():
    print("=" * 62)
    print("%s  -  环境自检" % APP_NAME)
    print("=" * 62)
    print("Python  :", sys.version.split()[0])
    print("解释器  :", sys.executable)
    print("平台    :", sys.platform)
    try:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        print("pygame  :", pygame.version.ver)
    except Exception as exc:
        print("pygame  : 缺失 ->", exc, " (pip install pygame)")
    if IS_WINDOWS:
        sim = InputSimulator()
        sim.move(1, 0)
        sim.move(-1, 0)
        sent, want = sim.probe()
        print("SendInput: %s (系统接受 %d/%d 个事件)"
              % ("可用" if sent == want else "注入被拒绝", sent, want))
    else:
        print("警告    : 非 Windows 平台，输入模拟不可用")
    pad = Gamepad()
    if not pad.available:
        print("手柄    :", pad.error)
        return 1
    print("手柄    : 找到 %d 个设备" % len(pad.names))
    for i, n in enumerate(pad.names):
        print("    [%d] %s" % (i, n))
    if pad.names:
        pad.poll()
        print("          实测: 按钮 %d / 摇杆 %d / 十字键 %d，本帧读到 %d 个按钮状态"
              % (pad.nbuttons, pad.naxes, pad.nhats, len(pad.buttons)))
    else:
        print("    (未插手柄；插上后重新运行)")
    print("=" * 62)
    return 0


HELP = """\
{name}  --  手柄当无线键盘 / 鼠标

  python gamepad_mapper.py                打开图形控制台（推荐）
  python gamepad_mapper.py --nogui        无界面运行，读 config.json
  python gamepad_mapper.py --list         列出手柄
  python gamepad_mapper.py --check        环境自检
  python gamepad_mapper.py --port 9000    指定控制台端口（默认 8765）
  python gamepad_mapper.py --no-browser   启动但不自动打开浏览器

默认映射（XBox 布局，可在控制台里任意改）：
  按钮0(A)   鼠标左键（点一下=单击，按住=按住不放）  按钮1(B)   鼠标右键
  按钮2(X)   鼠标双击                     按钮3(Y)   键盘 BACKSPACE（退格/删除）
  按钮4(LB)  键盘 ESC                     按钮5(RB)  键盘 R
  按钮6(返回) 开关映射                    按钮7(开始) 语音输入（Win+H）
  按钮8(LS)  键盘 TAB                     按钮9(RS)  键盘 ENTER
  按钮10     键盘 空格                    按钮11     连发 空格 15次/秒
  十字键↑↓   滚轮上下（连发 6 次/秒）    十字键←→  快退 / 快进（← / →，按一下跳一次）
  左摇杆     鼠标移动（快，灵敏度 1400，可单独调）
  右摇杆     鼠标移动（慢，灵敏度 500，可单独调）

  说明：播放器每响应一次方向键前进约 5 秒，所以十字键 ← → 是「按一下跳一次」，
        按住不放不会连续快进；想改成按住连续快进，把那一行的触发方式换成「连发」。

  Ctrl+F12   任何时候全局开关映射
""".format(name=APP_NAME)


def probe_existing(port):
    """检测该端口上是否已经跑着本程序，避免重复启动导致鼠标被点两遍。"""
    import urllib.request
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/api/ping" % port, timeout=0.7) as r:
            return b"gamepad-mapper" in r.read()
    except Exception:
        return False


def main(argv):
    if "--help" in argv or "-h" in argv or "/?" in argv:
        print(HELP)
        return 0
    if "--check" in argv:
        return check_env()
    if "--list" in argv:
        pad = Gamepad()
        if not pad.available:
            print(pad.error)
            return 1
        if not pad.names:
            print("未检测到手柄")
        for i, n in enumerate(pad.names):
            print("[%d] %s" % (i, n))
        return 0

    port = DEFAULT_PORT
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
        except Exception:
            pass

    cfg = load_config()
    if "--nogui" in argv or "--console" in argv:
        return run_nogui(cfg)

    # 已经在运行就不再开第二个实例（否则一次按键会点两下）
    if probe_existing(port):
        url = "http://127.0.0.1:%d/" % port
        print("检测到程序已在运行，直接打开面板：%s" % url)
        if "--no-browser" not in argv:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        return 0

    rt = Runtime(cfg)
    if not rt.pad.available:
        print("[错误] %s" % rt.pad.error)
        return 2
    return run_web(rt, port=port, open_browser=("--no-browser" not in argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
