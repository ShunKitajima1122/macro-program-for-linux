from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from evdev import InputDevice, UInput, ecodes, list_devices

DEFAULT_CONFIG_PATH = Path(__file__).with_name("macros.json")


# ---- hotkey parsing ( "<ctrl>+<shift>+e" ) ----
def _char_to_keycode(ch: str) -> int:
    ch = ch.lower()
    if "a" <= ch <= "z":
        return getattr(ecodes, f"KEY_{ch.upper()}")
    if "0" <= ch <= "9":
        return getattr(ecodes, f"KEY_{ch}")
    if ch == " ":
        return ecodes.KEY_SPACE

    # 追加：よく使う記号（US配列相当のキーコード）
    punct = {
        "`": ecodes.KEY_GRAVE,          # `
        "-": ecodes.KEY_MINUS,          # -
        "=": ecodes.KEY_EQUAL,          # =
        "[": ecodes.KEY_LEFTBRACE,      # [
        "]": ecodes.KEY_RIGHTBRACE,     # ]
        "\\": ecodes.KEY_BACKSLASH,     # \
        ";": ecodes.KEY_SEMICOLON,      # ;
        "'": ecodes.KEY_APOSTROPHE,     # '
        ",": ecodes.KEY_COMMA,          # ,
        ".": ecodes.KEY_DOT,            # .
        "/": ecodes.KEY_SLASH,          # /
    }
    if ch in punct:
        return punct[ch]

    raise ValueError(f"Unsupported char key: {ch!r}")



def parse_hotkey(spec: str) -> List[set[int]]:
    """
    Returns list of alternative-sets.
    Each element is a set of acceptable codes for that modifier/key.
    Example: "<ctrl>+e" => [{KEY_LEFTCTRL,KEY_RIGHTCTRL},{KEY_E}]
    """
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    out: List[set[int]] = []

    for p in parts:
        if p in ("<ctrl>", "<control>"):
            out.append({ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL})
        elif p == "<shift>":
            out.append({ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT})
        elif p == "<alt>":
            out.append({ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT})
        elif p in ("<meta>", "<super>", "<win>"):
            out.append({ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA})
        elif p.startswith("<f") and p.endswith(">"):
            n = int(p[2:-1])
            out.append({getattr(ecodes, f"KEY_F{n}")})
        elif len(p) == 1:
            out.append({_char_to_keycode(p)})
        else:
            raise ValueError(f"Unsupported hotkey token: {p!r}")

    return out


def hotkey_satisfied(pressed: set[int], req: List[set[int]]) -> bool:
    return all(any(code in pressed for code in alt) for alt in req)


# ---- macro input (uinput) ----
def parse_macro_key(raw: str) -> int:
    raw = raw.strip()
    if raw.startswith("Key."):
        name = raw.split(".", 1)[1]
        # Key.enter -> KEY_ENTER etc.
        mapping = {
            "enter": ecodes.KEY_ENTER,
            "esc": ecodes.KEY_ESC,
            "tab": ecodes.KEY_TAB,
            "space": ecodes.KEY_SPACE,
            "backspace": ecodes.KEY_BACKSPACE,
            "delete": ecodes.KEY_DELETE,
            "up": ecodes.KEY_UP,
            "down": ecodes.KEY_DOWN,
            "left": ecodes.KEY_LEFT,
            "right": ecodes.KEY_RIGHT,
            "shift": ecodes.KEY_LEFTSHIFT,
            "shift_l": ecodes.KEY_LEFTSHIFT,
            "shift_r": ecodes.KEY_RIGHTSHIFT,
            "ctrl": ecodes.KEY_LEFTCTRL,
            "ctrl_l": ecodes.KEY_LEFTCTRL,
            "ctrl_r": ecodes.KEY_RIGHTCTRL,
            "alt": ecodes.KEY_LEFTALT,
            "alt_l": ecodes.KEY_LEFTALT,
            "alt_r": ecodes.KEY_RIGHTALT,
        }
        if name.startswith("f") and name[1:].isdigit():
            return getattr(ecodes, f"KEY_F{int(name[1:])}")
        if name in mapping:
            return mapping[name]
        raise ValueError(f"Unsupported Key.*: {raw}")
    if len(raw) == 1:
        return _char_to_keycode(raw)
    raise ValueError(f"Unsupported key format: {raw}")


class HoldState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held: set[int] = set()

    def mark_down(self, code: int) -> None:
        with self._lock:
            self._held.add(code)

    def mark_up(self, code: int) -> None:
        with self._lock:
            self._held.discard(code)

    def release_all_return(self, ui: UInput) -> List[int]:
        with self._lock:
            codes = list(self._held)
            self._held.clear()
        for c in codes:
            try:
                ui.write(ecodes.EV_KEY, c, 0)
            except Exception:
                pass
        ui.syn()
        return codes

    def release_all(self, ui: UInput) -> None:
        with self._lock:
            codes = list(self._held)
            self._held.clear()
        for c in codes:
            try:
                ui.write(ecodes.EV_KEY, c, 0)
            except Exception:
                pass
        ui.syn()


def ensure_uinput() -> UInput:
    # ざっくり “ゲームで使いがちなキー＋マウス” を許可
    keys = [
        ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E, ecodes.KEY_F, ecodes.KEY_G,
        ecodes.KEY_H, ecodes.KEY_I, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_M, ecodes.KEY_N,
        ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_Q, ecodes.KEY_R, ecodes.KEY_S, ecodes.KEY_T, ecodes.KEY_U,
        ecodes.KEY_V, ecodes.KEY_W, ecodes.KEY_X, ecodes.KEY_Y, ecodes.KEY_Z,
        ecodes.KEY_0, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4,
        ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9,
        ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_ESC, ecodes.KEY_TAB,
        ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
        ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
        ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
    ] + [getattr(ecodes, f"KEY_F{i}") for i in range(1, 13)]

    events = {
        ecodes.EV_KEY: keys + [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
    }
    return UInput(events, name="macro-toggle-uinput", bustype=ecodes.BUS_USB)


def _wait_with_pause(seconds: float, stop_event: threading.Event, run_event: threading.Event) -> None:
    remaining = float(seconds)
    tick = 0.05  # 50ms刻み（止めた時の反応を良くする）
    while remaining > 0 and not stop_event.is_set():
        # pause中は時間を減らさない
        if not run_event.is_set():
            stop_event.wait(timeout=tick)
            continue

        t0 = time.monotonic()
        dt = min(tick, remaining)
        if stop_event.wait(timeout=dt):
            break
        remaining -= (time.monotonic() - t0)


def do_step(step: Dict[str, Any], stop_event: threading.Event, run_event: threading.Event, ui: UInput, hold: HoldState) -> None:
    t = step.get("type")

    if t == "wait":
        _wait_with_pause(float(step.get("seconds", 0)), stop_event, run_event)
        return

    if stop_event.is_set():
        return

    if t == "key":
        code = parse_macro_key(str(step["key"]))
        action = str(step.get("action", "tap"))
        if action == "tap":
            ui.write(ecodes.EV_KEY, code, 1)
            ui.write(ecodes.EV_KEY, code, 0)
            ui.syn()
            return
        if action == "press":
            ui.write(ecodes.EV_KEY, code, 1)
            ui.syn()
            hold.mark_down(code)
            return
        if action == "release":
            ui.write(ecodes.EV_KEY, code, 0)
            ui.syn()
            hold.mark_up(code)
            return
        raise ValueError("key.action must be tap/press/release")

    if t == "combo":
        raw_keys = [str(k) for k in step.get("keys", [])]
        codes = [parse_macro_key(rk) for rk in raw_keys]
        for c in codes:
            ui.write(ecodes.EV_KEY, c, 1)
        for c in reversed(codes):
            ui.write(ecodes.EV_KEY, c, 0)
        ui.syn()
        return

    if t == "mouse_click":
        button = str(step.get("button", "left"))
        count = int(step.get("count", 1))
        btn_code = ecodes.BTN_LEFT if button == "left" else ecodes.BTN_RIGHT
        for _ in range(max(1, count)):
            ui.write(ecodes.EV_KEY, btn_code, 1)
            ui.write(ecodes.EV_KEY, btn_code, 0)
            ui.syn()
        return

    if t == "mouse_button":
        button = str(step.get("button", "left"))
        action = str(step.get("action", "tap"))
        btn_code = ecodes.BTN_LEFT if button == "left" else ecodes.BTN_RIGHT

        if action == "tap":
            ui.write(ecodes.EV_KEY, btn_code, 1)
            ui.write(ecodes.EV_KEY, btn_code, 0)
            ui.syn()
            return

        if action == "press":
            ui.write(ecodes.EV_KEY, btn_code, 1)
            ui.syn()
            hold.mark_down(btn_code)  # 停止時に必ずreleaseされる
            return

        if action == "release":
            ui.write(ecodes.EV_KEY, btn_code, 0)
            ui.syn()
            hold.mark_up(btn_code)
            return

        raise ValueError('mouse_button.action must be "tap"/"press"/"release"')

    if t == "mouse_move":
        mode = str(step.get("mode", "relative"))
        x = int(step.get("x", 0))
        y = int(step.get("y", 0))
        if mode != "relative":
            raise ValueError('mouse_move.mode is "relative" only in uinput version')
        ui.write(ecodes.EV_REL, ecodes.REL_X, x)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, y)
        ui.syn()
        return

    if t == "mouse_scroll":
        dy = int(step.get("dy", 0))
        if dy != 0:
            ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, dy)
            ui.syn()
        return

    raise ValueError(f"Unknown step.type: {t}")


def pick_keyboard_device(config: Dict[str, Any]) -> InputDevice:
    path = config.get("input_device")
    if path:
        return InputDevice(str(path))

    # auto-pick: first device that looks like a keyboard
    for p in list_devices():
        dev = InputDevice(p)
        caps = dev.capabilities(verbose=False)
        keys = caps.get(ecodes.EV_KEY, [])
        if ecodes.KEY_A in keys and ecodes.KEY_LEFTCTRL in keys:
            return dev

    raise RuntimeError("Keyboard device not found. Set macros.json input_device to /dev/input/by-id/...-event-kbd")


class MacroTool:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.loop = bool(config.get("loop", False))
        self.macro: List[Dict[str, Any]] = list(config.get("macro", []))

        self.trigger_spec = str(config.get("trigger_hotkey") or "").strip()
        self.quit_spec = str(config.get("quit_hotkey") or "").strip()
        if not self.trigger_spec:
            raise ValueError('Set "trigger_hotkey" in macros.json (uinput版はhotkey推奨)')

        self.trigger_req = parse_hotkey(self.trigger_spec)
        self.quit_req = parse_hotkey(self.quit_spec) if self.quit_spec else None

        self.stop_event = threading.Event()
        self.run_event = threading.Event()  # set=実行, clear=一時停止

        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        self.ui = ensure_uinput()
        self.hold = HoldState()
        self._paused_restore: List[int] = []

        self.kbd = pick_keyboard_device(config)

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def is_paused(self) -> bool:
        return self.is_running() and (not self.run_event.is_set())

    def start(self) -> None:
        with self.lock:
            if self.is_running():
                return
            self.stop_event.clear()
            self.run_event.set()
            self._paused_restore.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print("[macro] started")

    def pause(self) -> None:
        with self.lock:
            if not self.is_running() or self.is_paused():
                return
            self.run_event.clear()
            # 押しっぱなしキーがあれば即解除して、再開時に戻せるよう保存
            self._paused_restore = self.hold.release_all_return(self.ui)
            print("[macro] paused")

    def resume(self) -> None:
        with self.lock:
            if not self.is_running() or not self.is_paused():
                return
            # pause時に押していたキーを押し直す
            for c in self._paused_restore:
                try:
                    self.ui.write(ecodes.EV_KEY, c, 1)
                    self.hold.mark_down(c)
                except Exception:
                    pass
            self.ui.syn()
            self._paused_restore.clear()
            self.run_event.set()
            print("[macro] resumed")

    def stop(self) -> None:
        self.stop_event.set()
        self.run_event.set()  # pause中でもスレッドが抜けられるように
        self.hold.release_all(self.ui)
        with self.lock:
            if self.is_running():
                print("[macro] stopping...")

    def trigger(self) -> None:
        # trigger_hotkey：開始 → 一時停止 → 再開
        if not self.is_running():
            self.start()
        elif self.is_paused():
            self.resume()
        else:
            self.pause()

    def request_quit(self) -> None:
        print("[macro] quitting...")
        self.stop()
        raise SystemExit(0)

    def _run(self) -> None:
        try:
            if self.loop:
                while not self.stop_event.is_set():
                    while (not self.stop_event.is_set()) and (not self.run_event.is_set()):
                        self.stop_event.wait(timeout=0.05)

                    for step in self.macro:
                        if self.stop_event.is_set():
                            break
                        while (not self.stop_event.is_set()) and (not self.run_event.is_set()):
                            self.stop_event.wait(timeout=0.05)
                        if self.stop_event.is_set():
                            break
                        do_step(step, self.stop_event, self.run_event, self.ui, self.hold)
            else:
                for step in self.macro:
                    if self.stop_event.is_set():
                        break
                    while (not self.stop_event.is_set()) and (not self.run_event.is_set()):
                        self.stop_event.wait(timeout=0.05)
                    if self.stop_event.is_set():
                        break
                    do_step(step, self.stop_event, self.run_event, self.ui, self.hold)
        finally:
            self.hold.release_all(self.ui)
            print("[macro] stopped")

    def listen_forever(self) -> None:
        print(f"[macro] device={self.kbd.path} name={self.kbd.name}")
        print(f"[macro] trigger={self.trigger_spec} quit={self.quit_spec}")
        print("[macro] listening (evdev)...")

        pressed: set[int] = set()
        trig_armed = True
        quit_armed = True

        for ev in self.kbd.read_loop():
            if ev.type != ecodes.EV_KEY:
                continue

            # ev.value: 1=down, 0=up, 2=repeat
            if ev.value == 1:
                pressed.add(ev.code)
            elif ev.value == 0:
                pressed.discard(ev.code)

            # quit
            if self.quit_req is not None:
                sat = hotkey_satisfied(pressed, self.quit_req)
                if sat and quit_armed:
                    self.request_quit()
                quit_armed = not sat

            # trigger (start/pause/resume)
            sat = hotkey_satisfied(pressed, self.trigger_req)
            if sat and trig_armed:
                self.trigger()
            trig_armed = not sat


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Linux(evdev/uinput) macro toggle tool")
    parser.add_argument(
        "config",
        nargs="?",
        help="Path to macro config JSON. If omitted, uses macros.json next to this script.",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_flag",
        help="Same as positional argument.",
    )
    args = parser.parse_args(argv)

    config_path_str = args.config_flag or args.config
    config_path = Path(config_path_str) if config_path_str else DEFAULT_CONFIG_PATH

    config = json.loads(config_path.read_text(encoding="utf-8"))
    tool = MacroTool(config)
    tool.listen_forever()


if __name__ == "__main__":
    main()
