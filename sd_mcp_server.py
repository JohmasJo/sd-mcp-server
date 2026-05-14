#!/usr/bin/env python3
"""
SDXL MCP Server — 通过 MCP 协议调用本地 Stable Diffusion WebUI 生图

使用 FastMCP 注册工具，返回的图片以内联 Image Content 形式传递，
MCP 客户端无需访问本地文件系统即可直接看到图片。

安装:
  pip install fastmcp

启动:
  python3 sd_mcp_server.py

注册到 MCP 客户端:
  {
    "mcpServers": {
      "sd-txt2img": {
        "command": "python3",
        "args": ["/path/to/sd_mcp_server.py"]
      }
    }
  }
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from mcp.types import TextContent

# ─── Configuration ────────────────────────────────────────────────────────────

SD_URL = os.environ.get("SD_WEBUI_URL", "http://127.0.0.1:7860")
OUTPUT_DIR = Path(os.environ.get("SD_OUTPUT_DIR", "/tmp/sd-output"))
LLAMA_SERVICE = os.environ.get("LLAMA_SERVICE", "llama-server.service")
LLAMA_HEALTH_URL = os.environ.get("LLAMA_HEALTH_URL", "http://127.0.0.1:5500/health")
VRAM_MANAGEMENT = os.environ.get("SD_VRAM_MANAGEMENT", "1") == "1"

# ─── MCP Server ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    "SDXL TXT2IMG Server",
)


# ─── VRAM 管理 ────────────────────────────────────────────────────────────────


def _systemctl(action: str) -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", action, LLAMA_SERVICE],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _llama_healthy(timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(LLAMA_HEALTH_URL)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def stop_llm() -> None:
    """停止 llama-server 释放 VRAM"""
    print("[VRAM] Stopping llama-server to free GPU memory...", file=sys.stderr)
    _systemctl("stop")
    time.sleep(1)


def start_llm() -> None:
    """启动 llama-server 并等待就绪"""
    print("[VRAM] Starting llama-server...", file=sys.stderr)
    _systemctl("start")
    print("[VRAM] Waiting for llama-server to be ready...", file=sys.stderr)
    if _llama_healthy():
        print("[VRAM] llama-server is ready!", file=sys.stderr)
    else:
        print("[VRAM] WARNING: llama-server did not respond in time.", file=sys.stderr)


# ─── SD API ────────────────────────────────────────────────────────────────────


def call_txt2img(
    prompt: str,
    negative_prompt: str = (
        "(score_4,score_3,score_2,score_1),worst quality,bad hands,bad feet,"
        "lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,"
        "fewer digits,cropped,worst quality,low quality,normal quality,jpeg "
        "artifacts,signature,watermark,username,blurry"
    ),
    steps: int = 20,
    width: int = 832,
    height: int = 1216,
    cfg_scale: float = 7.0,
    sampler_name: str = "Euler a",
    seed: int = -1,
    batch_size: int = 1,
) -> dict:
    """调用 SD WebUI txt2img API，返回结果"""

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
        "batch_size": batch_size,
    }

    url = f"{SD_URL}/sdapi/v1/txt2img"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"SD WebUI HTTP {e.code}: {e.reason}\n{e.read().decode()}")
    except Exception as e:
        raise RuntimeError(f"SD WebUI connection failed: {e}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_images: list[bytes] = []
    paths: list[str] = []
    info = json.loads(result.get("info", "{}"))

    for i, img_b64 in enumerate(result.get("images", [])):
        img_data = base64.b64decode(img_b64)
        raw_images.append(img_data)
        # 同时存到磁盘，方便本地取用
        seed_val = info.get("seed", "unknown")
        filename = f"{seed_val}_{i}.png"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(img_data)
        paths.append(str(filepath.resolve()))

    return {
        "images": raw_images,
        "paths": paths,
        "seed": info.get("seed", -1),
        "model": info.get("sd_model_name", ""),
        "info": info,
    }


# ─── FastMCP Tools ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="txt2img",
    description="在本地 Stable Diffusion WebUI 上根据文字描述生成图片，返回内联图片内容",
)
def txt2img_tool(
    prompt: str = ...,
    negative_prompt: str = (
        "(score_4,score_3,score_2,score_1),worst quality,bad hands,bad feet,"
        "lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,"
        "fewer digits,cropped,worst quality,low quality,normal quality,jpeg "
        "artifacts,signature,watermark,username,blurry"
    ),
    steps: int = 20,
    width: int = 832,
    height: int = 1216,
    cfg_scale: float = 7.0,
    sampler_name: str = "Euler a",
    seed: int = -1,
    batch_size: int = 1,
) -> list:
    """
    通过本地 Stable Diffusion WebUI 生成图片，返回内联图片内容。

    Args:
        prompt: 正向提示词（描述想要生成的画面）
        negative_prompt: 反向提示词（描述不想要的内容）
        steps: 采样步数，越多质量越高但越慢 (15-40)
        width: 图片宽度 (像素)
        height: 图片高度 (像素)
        cfg_scale: CFG 引导强度，越大越贴近提示词 (4-15)
        sampler_name: 采样器名称 (Euler a, DPM++ 2M Karras, etc.)
        seed: 随机种子，-1 为随机，相同种子可复现
        batch_size: 一次生成几张

    Returns:
        列表，包含内联图片 (Image) 和元信息 (TextContent)
    """
    if VRAM_MANAGEMENT:
        stop_llm()

    try:
        result = call_txt2img(
            prompt=prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            width=width,
            height=height,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            seed=seed,
            batch_size=batch_size,
        )
    finally:
        if VRAM_MANAGEMENT:
            start_llm()

    # 构建返回内容：图片 + 元信息
    content: list = []
    for img_data in result["images"]:
        content.append(Image(data=img_data, format="png"))

    content.append(TextContent(
        type="text",
        text=json.dumps({
            "seed": result["seed"],
            "model": result["model"],
            "batch_size": batch_size,
        }, indent=2, ensure_ascii=False),
    ))

    return content


@mcp.tool(
    name="get_sd_status",
    description="查看 SD WebUI 运行状态",
)
def get_sd_status() -> str:
    """检查本地 SD WebUI 是否在线，返回模型信息"""
    try:
        req = urllib.request.Request(f"{SD_URL}/sdapi/v1/sd-models")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        req2 = urllib.request.Request(f"{SD_URL}/sdapi/v1/options")
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            opts = json.loads(resp2.read().decode())
        return json.dumps({
            "status": "online",
            "models": [m["title"] for m in data],
            "current_model": opts.get("sd_model_checkpoint", "unknown"),
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "offline", "error": str(e)}, indent=2)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    print("=" * 50, file=sys.stderr)
    print(f"  SDXL MCP Server", file=sys.stderr)
    print(f"  SD WebUI: {SD_URL}", file=sys.stderr)
    print(f"  Output:   {OUTPUT_DIR.resolve()}", file=sys.stderr)
    print(f"  VRAM mgmt: {'ON' if VRAM_MANAGEMENT else 'OFF'}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
