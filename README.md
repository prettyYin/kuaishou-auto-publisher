# 快手自动发布助手

面向快手磁力金牛投放运营的 Windows 桌面自动化工具：在快手创作者服务平台逐条上传视频、填写广告语标题并发布，再回磁力金牛把素材名改回对应视频文件名。

## 目录说明

- `outputs/快手自动发布助手/`：工具源码、公共配置模板、使用说明和启动入口。
- `work/`：打包脚本、启动器源码和使用说明生成脚本。
- `outputs/快手自动发布助手-免安装版.zip`：本地构建产物，不进入 Git。

## 敏感文件

以下内容只属于运行电脑，不会进入 Git：

- 个人账号配置 `config/config.json`
- 运行状态 `runs/`
- 日志和页面截图 `logs/`
- 结果报表 `报表/`
- 免安装版 zip 和本地打包目录

仓库里只保留脱敏模板 `config/config.example.json`。

## 开发与自检

```powershell
cd outputs\快手自动发布助手
python -X utf8 -m app.selftest
```

## 打包免安装版

```powershell
python -X utf8 work\build_portable.py
```

## 使用说明

图文说明见 `outputs/快手自动发布助手/使用说明.html`。
