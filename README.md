# Macro Program For Linux

ホットキーで **マクロ開始／一時停止／再開（トグル）** できる常駐型ツールです。  
マクロは JSON に「キー入力」「待機」「マウス操作」などの手順を定義します。

- トリガを押すと **開始**
- 実行中にトリガを押すと **一時停止（押しっぱなしは必ず release）**
- 一時停止中にトリガを押すと **再開（押しっぱなし状態も復元）**
- 実行中に **トリガ以外のキーを押しても止まらない**
- 終了ホットキーで **即終了** できる

> 注意：Wayland セッションだと制限で動かない場合があります。  
> **Xorg/X11 セッション**を推奨します。

---

## ファイル構成

```

macro-program-for-linux/
macro_toggle.py
macros.json
README.md

````

---

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
cd ~/path/to/macro-program-for-linux
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install evdev
```

---

## 実行

```bash
source .venv/bin/activate
python3 macro_toggle.py
```

起動するとホットキー待機状態になります。

---

## 設定ファイル（JSON）の指定

デフォルトでは、スクリプトと同階層の `macros.json` を読みます。

別の JSON を使いたい場合：

```bash
python3 macro_toggle.py /path/to/your_macros.json
# または
python3 macro_toggle.py -c /path/to/your_macros.json
```

---

## macros.json の書き方

### JSONの注意（重要）

`macros.json` は **厳密なJSON**です。

* コメント不可（`//` や `#` はNG）
* 末尾カンマ不可
* 文字列は必ず `"` で囲む

検証：

```bash
python3 -m json.tool macros.json
```

---

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

### トリガ（開始／一時停止／再開・終了）

例：`Ctrl+Shift+E` で開始/一時停止/再開、`Ctrl+Shift+Q` で終了

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

* `true`：停止するまで（または終了ホットキーまで）繰り返す
* `false`：1回実行して終了（省略時は false）

---

## ホットキー書式（trigger_hotkey / quit_hotkey）

例：

* `"<ctrl>+<shift>+e"`
* `"<alt>+<f4>"`
* `"<ctrl>+["`
* `"<ctrl>+`"`（バッククォート）

使えるトークン：

* 修飾キー：`<ctrl>` / `<shift>` / `<alt>` / `<meta>`（`<super>`, `<win>` も可）
* Fキー：`<f1>` ～ `<f12>`
* 1文字キー：英数字・スペース・一部記号（後述）

---

## 1文字キーで指定できる記号

`key` や `hotkey` で、以下の **特殊記号を 1 文字で指定**できます（US配列相当のキーコード）。

* `` ` ``（バッククォート）
* `-` `=`
* `[` `]`
* `\`
* `;` `'`
* `,` `.`
* `/`

例：

```json
{ "type": "key", "key": "[", "action": "tap" }
```

```json
"trigger_hotkey": "<ctrl>+["
```

> JSON内で `\` を書くときはエスケープが必要です：`"\\"`

---

## macro ステップ仕様

`macro` は上から順に実行されます。

### wait（待機）

```json
{ "type": "wait", "seconds": 0.2 }
```

* 一時停止中は **待機時間が進みません**（再開すると続きから待ちます）

---

### key（キー操作）

* `action`: `"tap"` / `"press"` / `"release"`
* `key`: `"a"` のような1文字、または `"Key.enter"` 等

例：`a` を 10 秒押しっぱなし

```json
{ "type": "key", "key": "a", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "key", "key": "a", "action": "release" }
```

---

### combo（同時押し）

```json
{ "type": "combo", "keys": ["Key.ctrl_l", "c"] }
```

---

### mouse_click（クリック）

```json
{ "type": "mouse_click", "button": "left", "count": 2 }
```

* `button`: `"left"` / `"right"`
* `count`: 1=クリック、2=ダブルクリック

---

### mouse_button（クリック押しっぱなし）

* `action`: `"tap"` / `"press"` / `"release"`
* `button`: `"left"` / `"right"`

例：左クリックを 10 秒押しっぱなし

```json
{ "type": "mouse_button", "button": "left", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "mouse_button", "button": "left", "action": "release" }
```

---

### mouse_move（マウス移動）

uinput 版は原則相対移動（relative）を想定します。

```json
{ "type": "mouse_move", "mode": "relative", "x": 50, "y": -10 }
```

---

### mouse_scroll（スクロール）

```json
{ "type": "mouse_scroll", "dy": -200 }
```

---

## サンプル

### ゲーム用：W を押しっぱなし（トリガで一時停止／再開）

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

* トリガで一時停止すると、`w` は必ず release されます
* 再開すると、`w` を押し直して続きます

---

### 記号キーの例：`[` を押す（tap）

```json
{
  "input_device": "/dev/input/by-id/usb-XXXXXXXXXX-event-kbd",
  "trigger_hotkey": "<ctrl>+[",
  "quit_hotkey": "<ctrl>+<shift>+q",
  "loop": false,
  "macro": [
    { "type": "key", "key": "[", "action": "tap" }
  ]
}
```

---

## トラブルシューティング

### Keyboard device not found

`input_device` 未指定 or 自動判別不能です。
`/dev/input/by-id/...-event-kbd` を `input_device` に設定してください。

---

### Permission denied: /dev/input/...

`input` グループに入っていない可能性があります。

```bash
sudo usermod -aG input $USER
```

→ ログアウト/ログイン必須。

---

### Permission denied: /dev/uinput

`/dev/uinput` の権限や uinput モジュールが原因の可能性があります。

```bash
sudo modprobe uinput
ls -l /dev/uinput
```

---

### Waylandで動かない

Xorg/X11 セッションでログインしてください。

---

### オンラインゲームで効かない

ゲームやアンチチート側が仮想入力を無視する場合があります。
各ゲームの規約に従って利用してください。