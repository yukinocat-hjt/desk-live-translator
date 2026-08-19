# 桌面实时翻译

框选屏幕上的一块区域，本地 OCR 识别文字，再翻译成悬浮字幕。适合游戏（无边框窗口）、视频、网页和外文软件界面。

## 环境

- Windows 10/11
- Python 3.10+

```powershell
cd "桌面实时翻译软件"
# 若 python 不在 PATH，可用： & "$env:LOCALAPPDATA\Python\bin\python.exe"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

已经建好虚拟环境时，直接：

```powershell
.\.venv\Scripts\python.exe -m app
```

首次启动会加载 RapidOCR 模型，可能需要几秒。

## 用法

1. 点击 **框选区域**（或 `Ctrl+Alt+R`），拖出要识别的矩形。
2. 选择源语言 / 目标语言和翻译引擎。
3. 填写 API Key（可选）。不填则只显示 OCR 原文。
4. 点击 **开始翻译**（或 `Ctrl+Alt+S`）。字幕出现在选区下方。
5. `Ctrl+Alt+H` 显示 / 隐藏字幕。关闭控制面板会最小化到托盘。

配置保存在 `%APPDATA%\DeskTranslate\config.json`。

## 翻译引擎

- **有道智云**：在 [有道智云控制台](https://ai.youdao.com/) 创建应用，填入 App Key / Secret。
- **DeepL**：填入 API Key。免费版 Key 以 `:fx` 结尾，会走 `api-free.deepl.com`。
- **仅识别不翻译**：调试 OCR 时使用。

## 限制

- 独占全屏游戏通常截不到画面，请改用无边框窗口。
- 花字、低对比、艺术字体识别会不准。
- 本程序只做本机截屏识字，不注入其他进程。
