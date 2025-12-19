# Macro Toggle Tool (Linux MintとUbuntuで動作確認)

ホットキーで **マクロ開始/停止(トグル)**　できる常駐型ツールです。  
マクロは `macros.json` に「キー入力」「待機」「マウス操作」などの手順を定義します。

- トリガを押すと開始、もう一度押すと停止
- 実行中に **トリガ以外のキーを押しても止まらない**
- 停止時は **押しっぱなし中のキー／マウスボタンを必ず離す(release)**

> 注意：Wayland セッションだと制限で動かない場合があります。  
> **Xorg/X11 セッション**を推奨します。

## ファイル構成

```

macro-program-for-linux/
  macro_toggle.py
  macros.json
  README.md

````

## セットアップ

### 権限設定（必須）

このツールは以下を行います。

- 物理キーボードを読む：`/dev/input/...`
- 仮想入力を出す：`/dev/uinput`

そのため `input` グループと uinput モジュールが必要です。

```bash
sudo usermod -aG input $USER
sudo modprobe uinput
````

**ログアウト→ログイン**（または再起動）して反映してください。

確認：

```bash
groups
ls -l /dev/uinput
```

`groups` に `input` が含まれること、`/dev/uinput` が `root input` かつ `660` 付近であることを確認します。

---

### venv 作成とインストール

```bash
cd ~/path/to/Macro_Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install evdev
```

## 実行

```bash
source .venv/bin/activate
python macro_toggle.py
```

起動するとホットキー待機状態になります。

## macros.json の書き方

### JSONの注意（重要）

`macros.json` は **厳密なJSON**です。

* コメント不可（`//` や `#` はNG）
* 末尾カンマ不可
* 文字列は必ず `"` で囲む

検証：

```bash
python -m json.tool macros.json
```

### 必須項目

* `input_device`（Linux版は必須に近い）
* `trigger_hotkey`
* `macro`

推奨：

* `quit_hotkey`
* `loop`

---

### input_device の指定（重要）

キーボードの `event-kbd` を指定します。

探し方（推奨：by-id）：

```bash
ls -l /dev/input/by-id/ | grep -E 'kbd|keyboard'
```

見つからなければ：

```bash
ls -l /dev/input/by-path/ | grep -E 'kbd|keyboard'
```

`...-event-kbd` を `input_device` に **必ず** 設定してください。

---

### トリガ（開始/停止・終了）

例：`Ctrl+Shift+E` でトグル、`Ctrl+Shift+Q` で終了

```json
{
  "input_device": "/dev/input/by-id/usb-XXXXXXXXX-event-kbd",
  "trigger_hotkey": "<ctrl>+<shift>+e",
  "quit_hotkey": "<ctrl>+<shift>+q",
  "loop": true,
  "macro": []
}
```

---

### loop

* `true`：停止するまで繰り返す
* `false`：1回実行して終了（省略時は false）

## macro ステップ仕様

`macro` は上から順に実行されます。

### wait（待機）

```json
{ "type": "wait", "seconds": 0.2 }
```

### key（キー操作）

* `action`: `"tap"` / `"press"` / `"release"`
* `key`: `"a"` のような1文字、または `"Key.enter"` 等

例：a を 10 秒押しっぱなし

```json
{ "type": "key", "key": "a", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "key", "key": "a", "action": "release" }
```

### combo（同時押し）

```json
{ "type": "combo", "keys": ["Key.ctrl_l", "c"] }
```

### mouse_click（クリック）

```json
{ "type": "mouse_click", "button": "left", "count": 2 }
```

* `button`: `"left"` / `"right"`
* `count`: 1=クリック、2=ダブルクリック

### mouse_button（クリック押しっぱなし）

* `action`: `"tap"` / `"press"` / `"release"`
* `button`: `"left"` / `"right"`

例：左クリックを 10 秒押しっぱなし

```json
{ "type": "mouse_button", "button": "left", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "mouse_button", "button": "left", "action": "release" }
```

### mouse_move（マウス移動）

uinput 版は原則相対移動（relative）を想定します。

```json
{ "type": "mouse_move", "mode": "relative", "x": 50, "y": -10 }
```

---

### mouse_scroll（スクロール）

```json
{ "type": "mouse_scroll", "dx": 0, "dy": -200 }
```

## サンプル

### ゲーム用：W を押しっぱなし（停止するまで）

```json
{
  "input_device": "/dev/input/by-id/usb-XXXXXXXXXX-event-kbd",
  "trigger_hotkey": "<ctrl>+<shift>+e",
  "quit_hotkey": "<ctrl>+<shift>+q",
  "loop": true,
  "macro": [
    { "type": "key", "key": "w", "action": "press" },
    { "type": "wait", "seconds": 99999 }
  ]
}
```

トリガ再押下で停止すると、W は必ず release されます。

## トラブルシューティング

### Keyboard device not found

`input_device` 未指定 or 自動判別不能です。
`/dev/input/by-id/...-event-kbd` を `input_device` に設定してください。

### Permission denied: /dev/input/...

`input` グループに入っていない可能性があります。

```bash
sudo usermod -aG input $USER
```

→ ログアウト/ログイン必須。

### Waylandで動かない

Xorg/X11 セッションでログインしてください。

### オンラインゲームで効かない

ゲームやアンチチート側が仮想入力を無視する場合があります。
規約に従って利用してください。