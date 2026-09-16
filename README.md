# 闲鱼管家

<div align="center">

**闲鱼多账号自动回复与经营管理工具**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Electron](https://img.shields.io/badge/Electron-Desktop-47848F.svg)](https://www.electronjs.org/)
[![Vue](https://img.shields.io/badge/Vue-3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 简介

闲鱼管家面向闲鱼卖家场景，提供多账号客服自动回复、订单与发货管理，并配套 Windows 桌面客户端。

- 桌面端：本地窗口扫码登录，自动启动后端服务
- Web 端：浏览器访问管理后台，配置回复与发货规则
- 多账号：按账号隔离 Cookie 会话

后端基于 [xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply) 二次开发，本仓库补充 Electron 桌面端与打包能力。

---

## 功能

| 模块 | 说明 |
|------|------|
| 账号 | 扫码登录、多账号切换、Cookie 持久化、重新授权 |
| 回复 | 关键词回复、默认回复、商品专属回复、AI 议价 |
| 发货 | 卡券发货、延时发货、多规格、发货规则 |
| 订单 | 订单列表、状态刷新、收货信息 |
| 商品 | 商品管理、采集与上架相关能力 |
| 通知 | 消息通知渠道 |
| 桌面端 | 工作台、开机启动、内置运行时打包 |

---

## 快速开始

### 环境

- Python 3.11+
- Node.js 18+ / pnpm（仅开发前端或桌面端时需要）

### 后端

```bash
git clone https://github.com/shudaxiag/xianyu-guanjia.git
cd xianyu-guanjia
pip install -r requirements.txt
python Start.py
```

访问 http://127.0.0.1:8080  
默认账号：`admin` / `admin123`

### 桌面客户端（开发）

```bash
cd desktop-client
pnpm install
pnpm dev
```

### 打包

```bash
cd desktop-client
pnpm run prepare:runtime
pnpm run build:release
```

产物目录：`desktop-client/dist-out/`

---

## 目录结构

```text
├── Start.py                 # 后端入口
├── reply_server.py          # FastAPI 服务
├── ensure_admin.py          # 管理员初始化
├── requirements.txt
├── requirements-desktop.txt
├── desktop-client/          # Electron + Vue 客户端
├── frontend/                # Web 前端
├── utils/
└── static/
```

---

## 免责声明

本项目仅供学习与研究，请遵守闲鱼平台规则及相关法律法规。使用本软件产生的风险由使用者自行承担。

---

## 致谢

- [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply)

## License

MIT
