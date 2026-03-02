# 51CTO 课程下载器

一个用于下载 51CTO 已购课程的 Windows 桌面工具。

## 功能特性

- 扫码登录（51CTO APP / 微信）
- 自动获取已购课程列表
- 批量勾选课程一键下载
- 按课程分目录保存视频
- 断点续传（已下载自动跳过）
- 随机延迟避免反爬

## 使用方法

1. 下载 `51CTO-Downloader.exe`
2. 双击运行
3. 点击「扫码登录」→ 用 51CTO APP 或微信扫码
4. 点击「刷新」获取已购课程
5. 勾选要下载的课程
6. 点击「开始下载」

视频默认保存到：`用户目录/Videos/51CTO/`

## 目录结构

```
~/Videos/51CTO/
├── Python入门到精通/
│   ├── 001_课程介绍.mp4
│   ├── 002_环境搭建.mp4
│   └── ...
├── MySQL数据库实战/
│   ├── 001_MySQL安装.mp4
│   └── ...
```

## 技术实现

### 核心技术栈

| 组件 | 用途 |
|------|------|
| Playwright | 无头浏览器，模拟登录和页面操作 |
| PyInstaller | 打包成 Windows EXE |
| customtkinter | 现代 GUI 界面 |
| N_m3u8DL-RE | m3u8 视频下载 |

### 爬取流程

```
1. 扫码登录
   └─ Playwright 打开登录页 → 截取二维码 → 轮询检测登录成功 → 保存 Cookie

2. 获取课程列表
   └─ 加载「我的课程」页面 → JavaScript 提取课程卡片信息

3. 获取课时列表
   └─ 进入课程详情页 → 展开章节 → 提取所有课时链接

4. 抓取 m3u8 地址
   └─ 打开课时页 → 点击播放 → 监听网络请求捕获 m3u8 URL

5. 下载视频
   └─ 调用 N_m3u8DL-RE 下载 m3u8 → 保存为 MP4
```

### 反爬措施

- User-Agent 伪装 Chrome 浏览器
- `--disable-blink-features=AutomationControlled` 隐藏自动化特征
- Cookie 持久化保持登录状态
- 随机延迟 1.5-4 秒模拟人工操作
- 失败自动重试（最多 3 次）

## EXE 构建流程

### 本地构建

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 下载 Chromium
python -m playwright install chromium

# 3. 下载 N_m3u8DL-RE
# 从 https://github.com/nilaoda/N_m3u8DL-RE/releases 下载 win-x64 版本
# 解压得到 N_m3u8DL-RE.exe 放到项目根目录

# 4. 打包
python -m PyInstaller build.spec --clean --noconfirm
```

产物：`dist/51CTO-Downloader.exe`

### GitHub Actions 自动构建

项目使用 GitHub Actions 实现打 tag 自动构建发布：

**触发条件：**
```bash
git tag v1.x.x
git push origin v1.x.x
```

**构建流程 (`.github/workflows/build.yml`)：**
1. Windows runner 环境
2. 安装 Python 3.11
3. 安装依赖 + Chromium
4. 下载 N_m3u8DL-RE
5. PyInstaller 打包
6. 发布到 GitHub Releases

**关键配置：**
```yaml
permissions:
  contents: write  # 必须有写权限才能创建 Release
```

### build.spec 要点

```python
# 打包 Chromium 浏览器
(str(browsers_src), "pw-browsers")

# 打包下载工具
(str(n_exe), ".")

# 运行时设置环境变量
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_bundle / "pw-browsers")
```

## 项目结构

```
51cto_downloader/
├── app.py              # GUI 主程序
├── build.spec          # PyInstaller 配置
├── requirements.txt    # Python 依赖
├── .github/
│   └── workflows/
│       └── build.yml   # GitHub Actions 构建配置
└── cto51/
    ├── __init__.py
    ├── config.py       # 配置（URL、路径等）
    ├── browser.py      # Playwright 浏览器管理
    ├── auth.py         # 登录相关
    ├── courses.py      # 课程/课时抓取
    ├── capture.py      # m3u8 嗅探
    ├── download.py     # 调用 N_m3u8DL-RE
    └── utils.py        # 工具函数
```

## 依赖说明

```
customtkinter>=5.2.0   # GUI 框架
playwright>=1.42.0     # 浏览器自动化
pillow>=10.0.0         # 图片处理（二维码显示）
pyinstaller>=6.0.0     # 打包工具
```

## 注意事项

- 仅供学习交流，请勿用于商业用途
- 仅支持下载自己已购买的课程
- 请合理使用，避免对服务器造成压力

## License

MIT
