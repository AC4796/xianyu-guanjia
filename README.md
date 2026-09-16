# 闲鱼管家

<div align="center">

**闲鱼多账号自动回复 · 订单发货 · 桌面客户端一键使用**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Electron](https://img.shields.io/badge/Electron-Desktop-47848F.svg)](https://www.electronjs.org/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 简介

**闲鱼管家**是一套面向闲鱼卖家的自动化经营管理工具，支持：

- **桌面客户端**：Windows 解压即用，自动拉起本地服务，扫码绑定账号
- **Web 管理端**：浏览器访问本地服务，进行回复规则、订单、发货等配置
- **多账号隔离**：每个闲鱼号独立 Cookie 会话，互不串号

适合需要多店管理、自动客服回复、自动发货的卖家与工作室。

> 后端能力参考并二次开发自开源项目 [xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply)；本仓库在此基础上完善了 **Electron 桌面端**、开机自启、打包分发与一键启动体验。

---

## 功能一览

| 模块 | 能力 |
|------|------|
| 账号 | 扫码登录 / 多账号切换 / Cookie 持久化 / 重新授权 |
| 智能回复 | 关键词回复、默认回复、商品专属回复、AI 议价 |
| 自动发货 | 卡券发货、延时发货、多规格、发货规则 |
| 订单 | 订单列表、状态刷新、收货信息、批量处理 |
| 商品 | 商品管理、采集、上架相关能力 |
| 通知 | 消息通知渠道配置 |
| 桌面端 | 扫码窗口、工作台、开机启动、内置运行环境打包 |

---

## 两种使用方式

### 方式 A：桌面成品（推荐发给别人 / 自己日常用）

1. 下载 Release 中的 Windows 发布包（或使用本地打包目录 `desktop-client/dist-out/闲鱼管家-发给别人`）
2. **整包解压**，不要只拷贝单个 exe
3. 双击 `闲鱼管家\XianyuGuanjia.exe`
4. 等待本地服务自动启动后，用闲鱼 App **扫码登录**

说明：正式发布包装有内置 Python 运行环境，对方电脑一般**无需再安装 Python**。

### 方式 B：源码开发 / 自建服务

#### 环境要求

- Windows 10/11（桌面端）
- Python 3.11+
- Node.js 18+ / pnpm（改前端或桌面端时需要）

#### 1. 克隆仓库

```bash
git clone https://github.com/shudaxiag/xianyu-guanjia.git
cd xianyu-guanjia
```

> 若你的仓库名不同，请把上面地址换成你自己的仓库地址。

#### 2. 安装后端依赖

```bash
pip install -r requirements.txt
# 或仅桌面启动所需精简依赖：
# pip install -r requirements-desktop.txt
```

#### 3. 启动后端

```bash
python Start.py
```

浏览器访问：http://127.0.0.1:8080  
默认管理员：`admin` / `admin123`（请及时修改）

#### 4.（可选）启动桌面客户端开发模式

```bash
cd desktop-client
pnpm install
pnpm dev
```

#### 5.（可选）打包 Windows 客户端

```bash
cd desktop-client
pnpm run prepare:runtime   # 首次：下载并预置便携 Python + 依赖
pnpm run build:release     # 生成 dist-out/闲鱼管家-发给别人
```

---

## 目录结构

```text
闲鱼管家/
├── Start.py                 # 后端启动入口
├── reply_server.py          # FastAPI 主服务
├── ensure_admin.py          # 初始化管理员
├── requirements.txt         # 完整 Python 依赖
├── requirements-desktop.txt # 桌面端精简依赖
├── desktop-client/          # Electron + Vue 桌面客户端
│   ├── src/main/            # 主进程（自动拉起后端、本地网关）
│   ├── src/renderer/        # 界面
│   └── scripts/             # 打包 / 发布脚本
├── frontend/                # Web 前端源码（可选构建）
├── utils/                   # 工具与协议相关
└── static/                  # 静态资源
```

---

## 常见问题

**Q: 打开客户端提示后端不可达？**  
A: 请使用完整发布包（含 `resources/project` 与 `resources/python`），不要只发单个 exe。

**Q: 提示用户名或密码错误？**  
A: 这是内部管理会话，不是闲鱼账号。请使用最新桌面包；客户端会自动初始化 `admin`。

**Q: 可以把 1GB 成品直接提交进 Git 吗？**  
A: 不建议。源码走 GitHub 仓库；成品用 **GitHub Releases** 上传压缩包。

**Q: 多账号会不会串 Cookie？**  
A: 按账号隔离存储；仍建议固定网络环境，避免频繁异地切换触发平台风控。

---

## 截图

可将工作台、扫码登录、订单页截图放到 `docs/images/` 后在此引用：

```markdown
![工作台](docs/images/home.png)
![扫码登录](docs/images/login.png)
```

---

## 免责声明

本项目仅供学习与交流，请遵守闲鱼平台规则与当地法律法规。使用自动化能力造成的账号风险由使用者自行承担。

---

## 致谢

- [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply)
- FastAPI / Vue / Electron / Naive UI 等开源生态

---

## License

MIT
