# SDXL MCP Server

通过 [FastMCP](https://github.com/jlowin/fastmcp) 将本地 **Stable Diffusion WebUI** 封装成 MCP 工具，可供任何支持 MCP 的客户端直接调用（Claude Desktop、OpenClaw、Cursor 等）。

## 要求

- Python 3.10+
- 本地运行着 **Stable Diffusion WebUI**（默认 `http://127.0.0.1:7860`）
- 可选：`systemctl --user` 管理的 `llama-server.service`（VRAM 自动管理用）

## 安装

```bash
pip install fastmcp
```

## 启动

```bash
python3 sd_mcp_server.py
```

看到如下输出表示启动成功：

```
==================================================
  SDXL MCP Server
  SD WebUI: http://127.0.0.1:7860
  Output:   /tmp/sd-output
  VRAM mgmt: ON
==================================================
```

## 注册到 MCP 客户端

### Claude Desktop (`claude_desktop_config.json`)

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

### OpenClaw (`~/.openclaw/config.yaml` 或 `openclaw.yaml`)

```yaml
mcpServers:
  sd-txt2img:
    command: python3
    args:
      - /path/to/sd_mcp_server.py
```

## 可用工具

### `txt2img`

通过文本描述生成图片。

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | `string` | **必填** | 正向提示词 |
| `negative_prompt` | `string` | 内置 PonyXL 负面 | 反向提示词 |
| `steps` | `int` | `20` | 采样步数 (15-40) |
| `width` | `int` | `832` | 宽度 |
| `height` | `int` | `1216` | 高度 |
| `cfg_scale` | `float` | `7.0` | CFG 引导强度 |
| `sampler_name` | `string` | `Euler a` | 采样器 |
| `seed` | `int` | `-1` | 种子 (相同值可复现) |
| `batch_size` | `int` | `1` | 一次生成数量 |

**返回：** 图片内容列表（内联 ImageContent），最后一条为 TextContent 包含 `seed`、`model` 元信息。MCP 客户端可直接显示图片，无需访问本地文件系统。

### `get_sd_status`

检查 SD WebUI 是否在线，显示当前模型信息。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SD_WEBUI_URL` | `http://127.0.0.1:7860` | SD WebUI 地址 |
| `SD_OUTPUT_DIR` | `/tmp/sd-output` | 图片输出目录 |
| `SD_VRAM_MANAGEMENT` | `1` | 是否启用 VRAM 管理（生图时自动停启 llama-server） |
| `LLAMA_SERVICE` | `llama-server.service` | llama-server systemd 服务名 |
| `LLAMA_HEALTH_URL` | `http://127.0.0.1:5500/health` | llama-server 健康检查地址 |

## 示例

```python
# 在支持 MCP 的客户端中调用
result = client.call_tool("txt2img", {
    "prompt": "(score_9, score_8_up, score_7_up), masterpiece, best quality, 1girl, cat ears, green hair, pink eyes, cute catgirl, nekomimi, looking at viewer, smile",
    "steps": 25,
    "width": 832,
    "height": 1216,
    "seed": 42
})
```
