<div align="center">

<img src="desktop-client/resources/icon.png" alt="闲鱼管家" width="96" height="96" />

# 闲鱼管家

**多账号自动回复 · 订单发货 · Windows 桌面端**

[![Version](https://img.shields.io/badge/version-v2.0.1-brightgreen)](https://github.com/shudaxiag/xianyu-guanjia)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-111827)](https://github.com/shudaxiag/xianyu-guanjia)
[![Stars](https://img.shields.io/github/stars/shudaxiag/xianyu-guanjia?style=flat)](https://github.com/shudaxiag/xianyu-guanjia/stargazers)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

[Releases](https://github.com/shudaxiag/xianyu-guanjia/releases) ·
[Issues](https://github.com/shudaxiag/xianyu-guanjia/issues) ·
[QQ 交流群](#community)

</div>

---

## Introduction

闲鱼管家是一套面向闲鱼卖家的 **本地经营管理工具**：多账号扫码登录、客服自动回复、订单与发货规则，配套 **Electron 桌面客户端** 与 **FastAPI 管理后台**。

面向「多店 / 多号」场景设计——会话按账号隔离，桌面端可一键拉起本地后端，Web 端继续配置回复、卡券与发货策略。

后端基于 [xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply) 二次开发，本仓库补齐桌面端、内置运行时与 Windows 打包发布能力。

---

## Highlights

- **本地优先**：数据与 Cookie 落在本机，桌面端内置运行时可一键启动
- **多账号隔离**：按账号管理会话、回复规则与发货策略
- **客服自动化**：关键词 / 默认回复、商品专属回复、AI 议价
- **经营闭环**：订单、卡券发货、延时发货、商品采集与上架相关能力
- **Windows 交付**：Electron 客户端 + 发布打包脚本，开箱可用

---

## Features

| 模块 | 能力 |
|------|------|
| **账号** | 扫码登录、多账号切换、Cookie 持久化、重新授权 |
| **回复** | 关键词 / 默认回复、商品专属回复、AI 议价 |
| **发货** | 卡券发货、延时发货、多规格、发货规则 |
| **订单** | 订单列表、状态刷新、收货信息 |
| **商品** | 商品管理、采集与上架相关能力 |
| **桌面端** | 工作台、开机启动、内置运行时一键打包 |

---

## Quick Start

### Requirements

- Python 3.11+
- Node.js 18+ / pnpm（开发前端或桌面端时）

### Backend

```bash
git clone https://github.com/shudaxiag/xianyu-guanjia.git
cd xianyu-guanjia
pip install -r requirements.txt
python Start.py
```

打开 http://127.0.0.1:8080  
默认账号：`admin` / `admin123`

### Desktop (dev)

```bash
cd desktop-client
pnpm install
pnpm dev
```

### Release build

```bash
cd desktop-client
pnpm run prepare:runtime
pnpm run build:release
```

产物目录：`desktop-client/dist-out/`

---

## Repository Layout

```text
├── Start.py                 # 后端入口
├── reply_server.py          # FastAPI 服务
├── ensure_admin.py          # 管理员初始化
├── requirements.txt
├── requirements-desktop.txt
├── desktop-client/          # Electron + Vue 客户端
├── frontend/                # Web 前端
├── docs/assets/             # 文档与社区资源
├── utils/
└── static/
```

---

## Community

<div align="center">

**加入 QQ 交流群** — 获取更新、反馈问题、交流玩法

![QQ Group](https://img.shields.io/badge/QQ群-1106143585-12B7F5?logo=tencent-qq&logoColor=white)](#community)

群号：`1106143585`

打开 QQ → 搜索群号 → 申请加入即可。

</div>

---

## Support

如果这个项目对你有帮助，欢迎点个 ⭐ Star，这是对作者最大的鼓励。

开发与维护成本不低。**打赏完全自愿，绝不强制**——如果感觉还不错，想请作者喝杯咖啡、打赏一点小礼物，扫下方收款码即可，多少随意，心意到位就好。

<div align="center">

img src="docs/assets/wechat-pay.png" alt="微信支付打赏" width="280" />

<br/>

*微信扫码即可 · 金额随意 · 感谢支持*

</div>

---

## Disclaimer

本项目仅供学习与研究使用。请遵守闲鱼平台规则及相关法律法规；使用本软件产生的风险由使用者自行承担。

---

## Acknowledgments

- [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply)

## License

[MIT](LICENSE)
