# 上传到 GitHub · 操作说明（给你自己看）

你的账号：`shudaxiag`  
目标：源码进仓库展示；成品（约 1GB）走 Releases，不要塞进 Git。

---

## 一、你需要先配合完成的事（本机）

### 1）登录 GitHub（二选一）

**推荐：GitHub Desktop（你说已安装连接器）**

1. 打开 **GitHub Desktop**
2. File → Options → Accounts → 用浏览器登录 `shudaxiag`
3. 登录成功即可

**或用命令行：**

1. 打开 PowerShell，执行：`gh auth login`
2. 选 GitHub.com → HTTPS → 浏览器登录

登录好后告诉我「已登录」，我可以继续帮你创建仓库并推送。

### 2）在 GitHub 网站新建空仓库

1. 打开 https://github.com/new
2. Repository name 建议：`xianyu-guanjia`（英文名更好）
3. Public 或 Private 自选
4. **不要**勾选 “Add a README”（本地已有）
5. 点 Create repository

---

## 二、我这边会帮你做的事

1. 写好仓库首页 README（介绍 / 功能 / 安装 / 使用）——已完成  
2. 忽略大文件（`dist-out`、内置 Python、zip、数据库等）——已完成  
3. 提交源码变更  
4. 关联远程仓库并 `git push`  
5. （可选）教你把 `闲鱼管家-发给别人` 打成 zip，上传到 **Release**

---

## 三、成品怎么发（给别人下载用）

不要把 955MB 目录直接 commit。正确做法：

1. 把文件夹  
   `desktop-client\dist-out\闲鱼管家-发给别人`  
   打成 zip（例如 `闲鱼管家-windows.zip`）
2. GitHub 仓库页 → **Releases** → Draft a new release  
3. 填写版本号如 `v2.0.1`，上传 zip  
4. 在 README 的「桌面成品」处写上 Release 下载链接

---

## 四、注意

- Cookie、数据库、日志、`.env` 不要上传（已在 `.gitignore`）
- 仓库里的大 zip / exe 已忽略
- README 里的 clone 地址默认写成了  
  `https://github.com/shudaxiag/xianyu-guanjia.git`  
  若仓库名不同，创建后告诉我，我帮你改一致
