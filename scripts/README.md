# aibes-agent 一键脚本

这里提供了一键安装、更新和运行 aibes-agent 的脚本，支持 Windows 和类 Unix 系统。

## 文件说明

| 文件 | 用途 | 适用平台 |
|------|------|----------|
| `install.ps1` / `install.bat` | 一键安装 / 更新 | Windows |
| `run.ps1` / `run.bat` | 一键运行示例或自定义脚本 | Windows |
| `run-web.ps1` / `run-web.bat` | 一键启动 Web UI | Windows |
| `install.sh` | 一键安装 / 更新 | Linux / macOS / WSL |
| `run.sh` | 一键运行示例或自定义脚本 | Linux / macOS / WSL |
| `run-web.sh` | 一键启动 Web UI | Linux / macOS / WSL |

## Windows

### 双击运行（推荐新手）

在项目根目录直接双击：

1. 安装 / 更新依赖：双击 `install.bat`
2. 运行默认示例：双击 `run.bat`
3. 启动 Web UI：双击 `run-web.bat`

也可以进入 `scripts/` 目录双击对应的 `.bat` 文件。

### PowerShell 运行（更灵活）

```powershell
# 安装 / 更新（会自动 git pull，可跳过）
.\scripts\install.ps1
.\scripts\install.ps1 -NoGitPull

# 运行默认示例
.\scripts\run.ps1

# 运行指定脚本
.\scripts\run.ps1 examples/planner_demo.py

# 自动允许所有权限提示
.\scripts\run.ps1 -YesToAll

# 指定配置文件
.\scripts\run.ps1 -Config aibes-agent.yaml

# 启动 Web UI
.\scripts\run-web.ps1
.\scripts\run-web.ps1 -Host 0.0.0.0 -Port 8080
```

## Linux / macOS / WSL

```bash
# 安装 / 更新
./scripts/install.sh
./scripts/install.sh --no-git-pull

# 运行默认示例
./scripts/run.sh

# 运行指定脚本
./scripts/run.sh examples/planner_demo.py

# 自动允许所有权限提示
./scripts/run.sh --yes-to-all

# 指定配置文件
./scripts/run.sh --config aibes-agent.yaml

# 启动 Web UI
./scripts/run-web.sh
./scripts/run-web.sh --host 0.0.0.0 --port 8080
```

> 在 Linux/macOS 上首次运行 `.sh` 脚本前，可能需要执行 `chmod +x scripts/*.sh`。

## 脚本行为

1. **自动检测 Python**：要求 Python >= 3.11。
2. **自动创建虚拟环境**：在项目根目录创建 `.venv`，避免污染系统环境。
3. **自动安装依赖**：使用 `pip install -e ".[dev,cli,web,mcp,drilling,code_review,documents]"` 进行可编辑安装。
4. **自动拉取源码**：`install` 脚本默认会 `git pull`（可跳过）。
5. **虚拟环境缺失时自动安装**：`run` 和 `run-web` 脚本在 `.venv` 不存在时会自动调用安装脚本。

## 自定义 extras

如果不需要全部可选依赖，可在安装时指定：

```powershell
.\scripts\install.ps1 -Extras "cli,web,mcp"
```

```bash
./scripts/install.sh --extras "cli,web,mcp"
```
