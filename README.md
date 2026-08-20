# 桌面实时翻译

框选屏幕上的一块区域，本地 OCR 识别文字，再翻译成悬浮字幕。适合游戏（无边框窗口）、视频、网页和外文软件界面。

## 环境

- Windows 10/11
- Python 3.10+（源码运行）

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

打包好的程序在 `dist\桌面实时翻译\`，运行其中的 `桌面实时翻译.exe`（请复制整个文件夹，不要只拷 exe）。

首次启动会加载 RapidOCR 模型，可能需要几秒。

## 用法

1. 点击 **框选区域**（或 `Ctrl+Alt+R`），拖出要识别的矩形。框选时控制面板会先藏起来，避免挡住画面。
2. 拖动浅色边框可移动识别区，拉边角缩放。字幕条上方金色条可单独拖动。
3. 选择源语言 / 目标语言和翻译引擎。
4. 填写 API Key（可选）。不填则只显示 OCR 原文。
5. 点击 **开始翻译**（或 `Ctrl+Alt+S`）。字幕出现在选区下方。
6. `Ctrl+Alt+H` 显示 / 隐藏字幕。关闭控制面板会隐藏到托盘，点托盘图标可再打开。

### 绑定程序（可选）

不绑定则识别区是屏幕上的固定矩形，和以前一样。

绑定后：

- 识别框会跟随该窗口移动、缩放
- 尽量只截该窗口自己的画面，减少被其他界面挡住导致的误识
- 部分游戏若窗口捕获失败，会自动退回屏幕截图

操作：先框选区域，再 **点选窗口** 或 **选择程序**。**取消绑定** 即回到屏幕固定区域。绑定只在本次运行有效，关闭软件后不会记住上次窗口。

### 截图间隔

面板可调，最低约 30ms。真正耗时的是 OCR；文字几乎没变时会跳过识别。翻译在后台进行，不会卡住截图。

## 翻译引擎

- **有道智云**
  - 官网 / 控制台：<https://ai.youdao.com/>
  - 创建应用后填入 App Key / Secret。
- **DeepL**
  - 官网：<https://www.deepl.com/>
  - API 申请：<https://www.deepl.com/pro-api>
  - 查看 Key：<https://www.deepl.com/your-account/keys>
  - 填入 API Key。免费版 Key 以 `:fx` 结尾，会走 `api-free.deepl.com`。
- **仅识别不翻译**：调试 OCR 时使用。

语言、引擎、Key、间隔等保存在 `%APPDATA%\DeskTranslate\config.json`。

## 打包

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm DeskTranslate.spec
```

产物在 `dist\桌面实时翻译\`。

## 限制

- 独占全屏游戏通常截不到画面，请改用无边框窗口。
- 花字、低对比、艺术字体识别会不准。
- 绑定窗口后，部分游戏/反作弊可能截到黑屏，此时会退回屏幕截图。
- 本程序只做本机截屏识字，不注入其他进程。
