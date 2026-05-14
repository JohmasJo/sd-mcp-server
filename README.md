# SDXL MCP Server

通过 [FastMCP](https://github.com/jlowin/fastmcp) 将本地 **Stable Diffusion WebUI** 封装成 MCP 工具，返回的图片以内联 **ImageContent** 形式传递，MCP 客户端可直接显示图片，无需访问本地文件系统。

支持调用方：Claude Desktop、OpenClaw、Cursor、Airi 等任意支持 MCP 协议的客户端。

## 要求

- Python 3.10+
- 本地运行着 **Stable Diffusion WebUI**（默认 `http://127.0.0.1:7860`）
- 可选：`systemctl --user` 管理的 `llama-server.service`（VRAM 自动管理用，非必需时可关闭）

## 安装

```bash
pip install fastmcp
```

## 启动

### 基本启动（完全默认配置）

```bash
python3 sd_mcp_server.py
```

启动成功输出：

```
==================================================
  SDXL MCP Server
  SD WebUI: http://127.0.0.1:7860
  Output:   /tmp/sd-output
  VRAM mgmt: ON
==================================================
```

### 配置 SD WebUI 地址

#### 远程 SD WebUI

如果 SD 跑在另一台机器（或 Docker 里）：

```bash
SD_WEBUI_URL=http://192.168.1.100:7860 python3 sd_mcp_server.py
```

> ⚠️ 远程连接需要 SD WebUI 启动时加 `--listen` 参数：`python3 launch.py --listen`

#### 自定义端口

```bash
SD_WEBUI_URL=http://127.0.0.1:17860 python3 sd_mcp_server.py
```

### 关闭 VRAM 管理

如果没装 `llama-server`，或者不需要自动管理显存，关闭 VRAM 管理可避免启动报错：

```bash
SD_VRAM_MANAGEMENT=0 python3 sd_mcp_server.py
```

启动后能看到 `VRAM mgmt: OFF`

### 同时配置多个变量

```bash
SD_WEBUI_URL=http://10.0.0.5:7860 \
SD_OUTPUT_DIR=/data/sd-output \
SD_VRAM_MANAGEMENT=0 \
  python3 sd_mcp_server.py
```

### 持久化配置（建议）

在 shell 配置文件（`~/.bashrc`、`~/.zshrc`）中添加，这样每次启动都不用手动传：

```bash
export SD_WEBUI_URL="http://192.168.1.100:7860"
export SD_OUTPUT_DIR="$HOME/sd-output"
export SD_VRAM_MANAGEMENT=0
```

然后用 `source ~/.zshrc` 使其生效，之后直接 `python3 sd_mcp_server.py` 就会读取这些值。

## 注册到 MCP 客户端

### Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "sd-txt2img": {
      "command": "python3",
      "args": ["/path/to/sd_mcp_server.py"]
    }
  }
}
```

如果需要带环境变量：

```json
{
  "mcpServers": {
    "sd-txt2img": {
      "command": "python3",
      "args": ["/path/to/sd_mcp_server.py"],
      "env": {
        "SD_WEBUI_URL": "http://10.0.0.5:7860",
        "SD_VRAM_MANAGEMENT": "0"
      }
    }
  }
}
```

### OpenClaw

`~/.openclaw/config.yaml` 或 `openclaw.yaml`：

```yaml
mcpServers:
  sd-txt2img:
    command: python3
    args:
      - /path/to/sd_mcp_server.py
    env:
      SD_WEBUI_URL: http://192.168.1.100:7860
      SD_VRAM_MANAGEMENT: "0"
```

### Airi

在 Airi 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "sd-txt2img": {
      "command": "python3",
      "args": ["/path/to/sd_mcp_server.py"]
    }
  }
}
```

也支持 `env` 字段配置环境变量，参考上方 Claude Desktop 示例。

## 可用工具

### `txt2img`

通过文本描述生成图片。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | `string` | **必填** | 正向提示词（描述想要生成的画面） |
| `negative_prompt` | `string` | 内置 PonyXL 负面词 | 反向提示词 |
| `steps` | `int` | `20` | 采样步数，越多质量越高但越慢 (15-40) |
| `width` | `int` | `832` | 图片宽度（像素） |
| `height` | `int` | `1216` | 图片高度（像素） |
| `cfg_scale` | `float` | `7.0` | CFG 引导强度，越大越贴近提示词 (4-15) |
| `sampler_name` | `string` | `Euler a` | 采样器名称（如 `DPM++ 2M Karras`） |
| `seed` | `int` | `-1` | 随机种子，相同值可复现 |
| `batch_size` | `int` | `1` | 一次生成几张 |

**返回：** 包含内联图片（ImageContent）和元信息（TextContent）的内容列表。
元信息包含 `seed`、`model`、`batch_size`。

### `get_sd_status`

检查 SD WebUI 是否在线，并返回当前加载的模型信息。

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SD_WEBUI_URL` | `http://127.0.0.1:7860` | SD WebUI 的访问地址。远程时改为 `http://<IP>:<port>` |
| `SD_OUTPUT_DIR` | `/tmp/sd-output` | 图片同时保存到本地的目录（内联返回已包含图片，此目录仅供本地手动取用） |
| `SD_VRAM_MANAGEMENT` | `1` (开) | 设为 `0` 关闭 VRAM 自动管理。如果没有 `llama-server` 强烈建议关闭 |
| `LLAMA_SERVICE` | `llama-server.service` | `systemctl --user` 管理的 llama-server 服务名 |
| `LLAMA_HEALTH_URL` | `http://127.0.0.1:5500/health` | llama-server 健康检查接口地址 |

## 常见场景配置示例

### 默认本地 SD → 直接启动

```bash
python3 sd_mcp_server.py
```

### SD 在远程服务器 + 无 VRAM 管理

```bash
SD_WEBUI_URL=http://192.168.1.200:7860 SD_VRAM_MANAGEMENT=0 python3 sd_mcp_server.py
```

### SD 在 Docker 容器中

如果 Docker 暴露的端口是 17860：

```bash
SD_WEBUI_URL=http://127.0.0.1:17860 python3 sd_mcp_server.py
```

### 在另一台机器上运行本 MCP Server（通过环境变量配置远程 SD）

```bash
# 在机器 A 上运行 MCP Server，连接机器 B 的 SD
SD_WEBUI_URL=http://10.0.0.50:7860 \
SD_VRAM_MANAGEMENT=0 \
  python3 sd_mcp_server.py
```

## 调用示例

```python
# 在支持 MCP 的客户端中调用 txt2img
result = client.call_tool("txt2img", {
    "prompt": "(score_9, score_8_up, score_7_up), masterpiece, best quality, 1girl, cat ears, green hair, pink eyes, cute catgirl, nekomimi, looking at viewer, smile",
    "steps": 25,
    "width": 832,
    "height": 1216,
    "seed": 42
})
```

```python
# 检查 SD 状态
status = client.call_tool("get_sd_status")
```
