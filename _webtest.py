# -*- coding: utf-8 -*-
"""Web 控制台冒烟测试：真实起服务、真实 HTTP 请求、真实写配置，最后自动退出。"""
import json, sys, threading, time
import urllib.request as U
import gamepad_mapper as G

PORT = 8791
BASE = "http://127.0.0.1:%d" % PORT
FAIL = []


def http(path, data=None):
    url = BASE + path
    if data is None:
        with U.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    req = U.Request(url, data=json.dumps(data).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
    with U.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  <- " + str(extra)))
    if not cond:
        FAIL.append(name)


def driver(rt):
    time.sleep(1.2)
    try:
        st, body = http("/")
        check("GET / 返回页面", st == 200 and "按键映射表" in body, st)
        check("页面动作选项已注入",
              '"none"' in body and '"mouse_double"' in body and '"voice"' in body
              and '"key_combo"' in body)
        check("无未替换占位符", "__ACTIONS__" not in body and "__MODES__" not in body)

        st, body = http("/api/state")
        s = json.loads(body)
        check("GET /api/state", st == 200 and "rows" in s and "device" in s, body[:120])
        check("状态含映射表行", len(s["rows"]) >= 16, len(s["rows"]))
        check("状态含 enabled", isinstance(s["enabled"], bool))
        check("状态含统计", "stats" in s and "clicks" in s["stats"])

        st, body = http("/api/config")
        c = json.loads(body)
        check("GET /api/config", st == 200 and c["buttons"]["0"]["action"] == "mouse_left")

        http("/api/cmd", {"cmd": "toggle"})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        check("toggle 生效(暂停)", s["enabled"] is False, s["enabled"])
        http("/api/cmd", {"cmd": "toggle"})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        check("toggle 生效(恢复)", s["enabled"] is True, s["enabled"])

        http("/api/cmd", {"cmd": "rows", "value": {"0": {"action": "mouse_double",
                                                         "mode": "tap", "hz": 33, "key": ""}}})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        row0 = [r for r in s["rows"] if r["idx"] == 0][0]
        check("改键写入并回读", row0["action"] == "mouse_double" and row0["hz"] == 33, row0)

        http("/api/cmd", {"cmd": "config", "value": {"mouse": {"sensitivity": 2222}}})
        time.sleep(0.4)
        c = json.loads(http("/api/config")[1])
        check("改设置写入并回读", c["mouse"]["sensitivity"] == 2222, c["mouse"])

        # 右摇杆滚轮：整段设置写入后必须逐项回读正确，且不能挤掉别的设置
        http("/api/cmd", {"cmd": "config", "value": {"mouse": {
            "right_stick_scroll": True,
            "scroll": {"axis": 3, "speed": 3.5, "deadzone": 0.30,
                       "exponent": 2.4, "linear_mix": 0.4, "smooth": 0.4,
                       "limit": 6, "invert": True}}}})
        time.sleep(0.4)
        c = json.loads(http("/api/config")[1])
        sc = c["mouse"]["scroll"]
        check("滚轮设置写入并回读",
              c["mouse"]["right_stick_scroll"] is True and sc["speed"] == 3.5
              and sc["deadzone"] == 0.30 and sc["exponent"] == 2.4
              and sc["smooth"] == 0.4 and sc["limit"] == 6
              and sc["invert"] is True, sc)
        check("滚轮设置未挤掉其它设置", c["mouse"]["sensitivity"] == 2222, c["mouse"])

        s = json.loads(http("/api/state")[1])
        check("状态含实时滚动速率", "scroll_rate" in s, sorted(s.keys()))
        check("状态含累计滚动格数", "scrolls" in s["stats"], s["stats"])

        # 触发方式：单点(tap) / 连发(rapid) 必须能独立切换且回读正确
        http("/api/cmd", {"cmd": "rows", "value": {"0": {"action": "mouse_left",
                                                         "mode": "tap", "hz": 20, "key": ""}}})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        row0 = [r for r in s["rows"] if r["idx"] == 0][0]
        check("切换为单点(tap)并回读", row0["mode"] == "tap" and row0["action"] == "mouse_left", row0)

        http("/api/cmd", {"cmd": "save"})
        time.sleep(0.3)
        check("单点写入落盘", G.load_config()["buttons"]["0"]["mode"] == "tap",
              G.load_config()["buttons"]["0"])

        # 语音输入：组合键与动作都要能写入并回读
        http("/api/cmd", {"cmd": "config", "value": {"voice_hotkey": "ctrl+alt+v"}})
        time.sleep(0.4)
        c = json.loads(http("/api/config")[1])
        check("语音输入组合键写入并回读", c.get("voice_hotkey") == "ctrl+alt+v",
              c.get("voice_hotkey"))

        http("/api/cmd", {"cmd": "rows", "value": {"4": {"action": "voice",
                                                         "mode": "tap", "hz": 20, "key": ""}}})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        row4 = [r for r in s["rows"] if r["idx"] == 4][0]
        check("语音输入动作写入并回读", row4["action"] == "voice", row4)

        # 面板只发「被改动的字段」，服务端必须**合并**而不是整行替换。
        # 曾经写成 btns[k] = v：在面板里只改一下「频率」那一格，同一行的
        # action / mode / key 会被一起抹掉 —— 十字键就此失效（真出过事故）。
        http("/api/cmd", {"cmd": "rows", "value": {"4": {"hz": 3.5}}})
        time.sleep(0.4)
        s = json.loads(http("/api/state")[1])
        row4 = [r for r in s["rows"] if r["idx"] == 4][0]
        check("只改一个字段不会抹掉整行（合并而非替换）",
              row4["action"] == "voice" and row4["mode"] == "tap"
              and float(row4["hz"]) == 3.5, row4)
        check("单字段改动也正确落盘",
              G.load_config()["buttons"]["4"].get("action") == "voice",
              G.load_config()["buttons"]["4"])

        http("/api/cmd", {"cmd": "rescan"})
        time.sleep(0.5)
        check("rescan 不崩溃", True)

        http("/api/cmd", {"cmd": "quit"})
    except Exception as exc:
        check("驱动线程异常", False, repr(exc))
        rt.quit = True


# 测试会真的写配置，先把原始文件整份备份下来，结束后逐字恢复
try:
    with open(G.CONFIG_PATH, "rb") as _f:
        _config_backup = _f.read()
except OSError:
    _config_backup = b""

rt = G.Runtime(G.load_config())
if not rt.pad.available:
    print("pygame 不可用:", rt.pad.error)
    sys.exit(2)
threading.Thread(target=driver, args=(rt,), daemon=True).start()
rc = G.run_web(rt, port=PORT, open_browser=False)

# 用原始字节整份还原，比逐项猜「测了什么、要改回什么」可靠得多。
# （之前的硬编码还原曾把用户的「单点」设置覆盖回「连发」。）
try:
    with open(G.CONFIG_PATH, "wb") as f:
        f.write(_config_backup)
    print("已还原测试前的配置（原始字节逐字恢复）")
except Exception as exc:
    print("还原配置失败：%r" % (exc,))

print("-" * 46)
print("失败 %d 项" % len(FAIL), FAIL)
sys.exit(1 if FAIL else 0)

print("-" * 46)
print("失败 %d 项" % len(FAIL), FAIL)
sys.exit(1 if FAIL else 0)
