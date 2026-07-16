# 打包与安装指南 (Packaging & Install)

## 给别人打包(你这边,3 步)

```powershell
# 在项目根目录 — 打出干净的发行包(只含代码,不含 venv/输出/瓦片,~几 MB)
git archive -o WildfireHazardDetection.zip HEAD
```

把 `WildfireHazardDetection.zip` 发给对方(网盘 / U 盘均可)。

> 想让对方**免下载模型/地图**?打完 zip 后,把你的 `models/` 和 `map/` 文件夹
> 复制进对方解压后的目录即可(这两个目录不进 git,需要手动带)。

## 对方安装(4 步)

1. 安装 **Python 3.13**(python.org,勾选 *Add python.exe to PATH*)
2. 解压 zip 到任意目录(建议路径不含中文/空格)
3. 双击 **`install.bat`** —— 自动建 venv、装 PyTorch(CUDA,失败自动退 CPU 版)、
   装依赖、创建桌面快捷方式(需联网一次,约 4 GB 依赖)
4. 双击桌面 **"Wildfire Hazard Detection"** —— 原生窗口打开,之后全离线运行

首次检测会自动下载火焰/烟雾模型(或联网时在 Settings → *Download missing models*);
卫星地图在 Map 页 / Settings 页一键下载当前区域。

## 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | Windows 10/11(Mac 代码兼容 MPS/CPU,未实测;快捷方式脚本仅 Windows) |
| Python | 3.13 |
| GPU | 任意 NVIDIA 显卡(自动用 CUDA);无 GPU 走 CPU,速度慢但可用 |
| 磁盘 | ~10 GB(依赖 + 模型) |
| 网络 | 仅安装时需要;运行全离线 |

## 为什么不是单文件 setup.exe?

PyTorch CUDA + DeepForest 打进 PyInstaller 体积 8 GB+ 且极易出 DLL 兼容问题。
"干净 zip + install.bat" 是 ML 桌面应用的务实做法:发行包小、装完体验与安装版软件相同
(桌面图标、原生窗口、无终端)。
