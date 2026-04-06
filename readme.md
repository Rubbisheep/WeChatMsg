# WeChatMsg Restored

这是一个基于残留源码整理出来的恢复版说明。

## 当前可用范围

当前环境下的使用说明如下：

- 仅微信 `3.9.12` 版本可以提取聊天记录
- 可提取的是 `4.0.3` 更新之前的那部分聊天记录

## 关键限制

微信 `4.0.3` 更新之后，数据库的存储逻辑发生了变化。

这会带来两个结果：

1. `4.0.3` 之后的数据不再沿用旧版 `Msg` 这一套存储方式
2. 当前这份恢复版代码无法导出 `3` 月之后的聊天记录

说明如下：

- `3` 月之前的老数据，可以通过微信 `3.9.12` 提取
- `3` 月之后的新数据，因为数据库存储逻辑变化，当前无法直接导出

## 对 3 月之后聊天记录的建议

对于 `3` 月之后的聊天记录，目前只能考虑手动方案，例如：

- 手动截图
- 手动复制文本
- 其他人工整理方式

当前仓库不保证可以自动导出这部分数据。

## 使用方式

### 1. 安装依赖

```powershell
cd d:\code\ClaudeCode\WeChatMsg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 启动恢复版 GUI

```powershell
cd d:\code\ClaudeCode\WeChatMsg
python restored_gui.py
```

### 3. 提取旧版聊天记录

操作步骤：

1. 安装并登录微信 `3.9.12`
2. 运行 `python restored_gui.py`
3. 在 GUI 里把 `Scan version` 选为 `3`
4. 点击 `Scan accounts`
5. 选中账号后点击 `Decrypt selected account`
6. 成功后 `DB dir` 会自动指向 `restored_output\<wxid>\Msg`
7. 点击 `Load contacts`
8. 选择联系人后导出

## 支持的导出格式

当前 GUI 支持：

- `html`
- `txt`
- `ai_txt`
- `markdown`
- `xlsx`
- `docx`

并额外支持：

- 仅导出“我发送的消息”

## 隐私说明

仓库已经在 `.gitignore` 中忽略这些本地内容：

- `.venv/`
- `exports/`
- `restored_output/`
- `__pycache__/`
- `*.db-shm`
- `*.db-wal`
- `日志文件-*.log`

这些目录和文件通常包含本地环境、导出结果、解密后的数据库和日志，不应提交到远程仓库。
