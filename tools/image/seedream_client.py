#!/usr/bin/env python3
"""
Seedream 4.5 API Client for Image Generation
火山引擎 Seedream 图片生成客户端

Based on official API documentation:
https://www.volcengine.com/docs/82379/1399028

Supports: text-to-image, image-to-image, multi-image fusion, group image generation.
"""
import os
import base64
import requests
from pathlib import Path
from typing import Optional, List, Union
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class SeedreamClient:
    """
    火山引擎 Seedream 图片生成API客户端

    使用方式:
        client = SeedreamClient(api_key=os.getenv('VOLCENGINE_API_KEY'))

        # 文生图
        paths = client.text_to_image(
            prompt='咖啡广告海报，暖色调，写实风格',
            output_dir=Path('data/media/20260217_120000')
        )

        # 图生图
        paths = client.image_to_image(
            prompt='将背景改为海滩',
            image_paths=[Path('input.jpg')],
            output_dir=Path('data/media/20260217_120000')
        )
    """

    BASE_URL = "https://ark.cn-beijing.volces.com"
    ENDPOINT = "/api/v3/images/generations"

    def __init__(self, api_key: str, model: str = None):
        """
        初始化客户端

        Args:
            api_key: 火山引擎API密钥 (VOLCENGINE_API_KEY)
            model: 模型ID (默认从.env读取SEEDREAM_MODEL)
        """
        self.api_key = api_key
        self.model = model or os.getenv('SEEDREAM_MODEL', 'doubao-seedream-4-5-251128')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def _encode_image_base64(self, image_path: Path) -> str:
        """将图片编码为base64字符串"""
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')

    def _prepare_image_param(self, image_paths: List[Path]) -> Union[str, List[str]]:
        """
        准备 image 参数：本地文件转 base64，URL 直接使用。

        Args:
            image_paths: 图片路径列表（可以是本地文件或 URL 字符串）

        Returns:
            单图时返回字符串，多图返回列表
        """
        images = []
        for p in image_paths:
            p_str = str(p)
            if p_str.startswith('http://') or p_str.startswith('https://'):
                images.append(p_str)
            else:
                path = Path(p)
                if not path.exists():
                    raise FileNotFoundError(f"参考图不存在: {path}")
                # 检查文件大小 (限制 10MB)
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > 10:
                    raise ValueError(f"参考图过大: {size_mb:.1f}MB (限制 10MB)")
                images.append(self._encode_image_base64(path))

        if len(images) == 1:
            return images[0]
        return images

    def generate_image(
        self,
        prompt: str,
        images: Optional[List[Path]] = None,
        size: str = "2K",
        watermark: bool = False,
        multi_image: bool = False,
        max_images: int = 4,
        response_format: str = "url",
    ) -> List[str]:
        """
        统一的图片生成方法。

        Args:
            prompt: 图片描述提示词
            images: 参考图路径列表（可选）
            size: 输出尺寸 ("2K", "4K", 或 "宽x高" 如 "2048x2048")
            watermark: 是否添加水印
            multi_image: 是否生成组图
            max_images: 组图数量 (multi_image=True 时有效)
            response_format: 返回格式 ("url" 或 "b64_json")

        Returns:
            图片 URL 列表（单图时列表长度=1）
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "watermark": watermark,
            "response_format": response_format,
            "stream": False,
        }

        # 添加参考图
        if images:
            payload["image"] = self._prepare_image_param(images)
            if not multi_image:
                payload["sequential_image_generation"] = "disabled"

        # 组图模式
        if multi_image:
            payload["sequential_image_generation"] = "auto"
            payload["sequential_image_generation_options"] = {
                "max_images": max_images
            }

        mode = "文生图"
        if images and multi_image:
            mode = f"图生组图 ({len(images)}张参考图 → {max_images}张)"
        elif images:
            mode = f"图生图 ({len(images)}张参考图)"
        elif multi_image:
            mode = f"文生组图 (→ {max_images}张)"

        print(f"📤 创建图片生成任务...")
        print(f"   模型: {self.model}")
        print(f"   模式: {mode}")
        print(f"   尺寸: {size}")

        try:
            response = self.session.post(
                f"{self.BASE_URL}{self.ENDPOINT}",
                json=payload,
                timeout=120  # 图片生成可能需要较长时间
            )
            response.raise_for_status()

            result = response.json()

            # 检查API错误响应 (有些错误返回200但body里有error字段)
            if 'error' in result:
                err = result['error']
                err_msg = err.get('message', str(err))
                err_code = err.get('code', 'unknown')
                raise ValueError(f"API返回错误 (code={err_code}): {err_msg}")

            # 响应格式: {"data": [{"url": "..."}, ...]} 或 {"data": [{"b64_json": "..."}, ...]}
            data = result.get('data', [])
            if not data:
                raise ValueError(f"API返回格式错误，未找到data字段: {result}")

            urls = []
            for item in data:
                if response_format == "url":
                    url = item.get('url')
                    if url:
                        urls.append(url)
                else:
                    b64 = item.get('b64_json')
                    if b64:
                        urls.append(b64)

            if not urls:
                raise ValueError(f"API返回数据中没有图片: {result}")

            print(f"✅ 图片生成完成! 共 {len(urls)} 张")
            return urls

        except requests.exceptions.RequestException as e:
            print(f"❌ API调用失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   状态码: {e.response.status_code}")
                print(f"   响应内容: {e.response.text}")
            raise

    def download_image(self, url: str, output_path: Path) -> Path:
        """
        下载生成的图片

        Args:
            url: 图片下载链接
            output_path: 保存路径
        """
        print(f"📥 下载图片: {output_path.name}")

        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = output_path.stat().st_size / 1024  # KB
            print(f"✅ 下载完成: {file_size:.1f} KB")
            return output_path

        except requests.exceptions.RequestException as e:
            print(f"❌ 下载失败: {e}")
            raise

    # ========================================================================
    # 便捷方法：一步到位的图片生成 + 下载
    # ========================================================================

    def text_to_image(
        self,
        prompt: str,
        output_dir: Path,
        size: str = "2K",
        watermark: bool = False,
    ) -> List[Path]:
        """
        文生图（纯文本输入，单图输出）

        Args:
            prompt: 图片描述
            output_dir: 输出目录
            size: 输出尺寸
            watermark: 是否添加水印

        Returns:
            输出图片路径列表
        """
        print(f"\n{'='*60}")
        print(f"🎨 文生图: {prompt[:50]}...")
        print(f"{'='*60}")

        urls = self.generate_image(
            prompt=prompt, size=size, watermark=watermark
        )

        paths = []
        for i, url in enumerate(urls):
            output_path = output_dir / f"image_{i+1}.png"
            self.download_image(url, output_path)
            paths.append(output_path)

        print(f"{'='*60}\n")
        return paths

    def image_to_image(
        self,
        prompt: str,
        image_paths: List[Path],
        output_dir: Path,
        size: str = "2K",
        watermark: bool = False,
    ) -> List[Path]:
        """
        图生图（参考图 + 文本输入，单图输出）

        Args:
            prompt: 编辑指令
            image_paths: 参考图路径列表
            output_dir: 输出目录
            size: 输出尺寸
            watermark: 是否添加水印

        Returns:
            输出图片路径列表
        """
        print(f"\n{'='*60}")
        ref_names = ', '.join(str(p.name) if isinstance(p, Path) else str(p)[:30] for p in image_paths)
        print(f"🎨 图生图: [{ref_names}] + \"{prompt[:40]}...\"")
        print(f"{'='*60}")

        urls = self.generate_image(
            prompt=prompt, images=image_paths, size=size, watermark=watermark
        )

        paths = []
        for i, url in enumerate(urls):
            output_path = output_dir / f"image_{i+1}.png"
            self.download_image(url, output_path)
            paths.append(output_path)

        print(f"{'='*60}\n")
        return paths

    def text_to_images(
        self,
        prompt: str,
        output_dir: Path,
        max_images: int = 4,
        size: str = "2K",
        watermark: bool = False,
    ) -> List[Path]:
        """
        文生组图（纯文本输入，多图输出）

        Args:
            prompt: 图片描述
            output_dir: 输出目录
            max_images: 生成图片数量
            size: 输出尺寸
            watermark: 是否添加水印

        Returns:
            输出图片路径列表
        """
        print(f"\n{'='*60}")
        print(f"🎨 文生组图 ({max_images}张): {prompt[:50]}...")
        print(f"{'='*60}")

        urls = self.generate_image(
            prompt=prompt, size=size, watermark=watermark,
            multi_image=True, max_images=max_images
        )

        paths = []
        for i, url in enumerate(urls):
            output_path = output_dir / f"image_{i+1}.png"
            self.download_image(url, output_path)
            paths.append(output_path)

        print(f"{'='*60}\n")
        return paths

    def image_to_images(
        self,
        prompt: str,
        image_paths: List[Path],
        output_dir: Path,
        max_images: int = 4,
        size: str = "2K",
        watermark: bool = False,
    ) -> List[Path]:
        """
        图生组图（参考图 + 文本输入，多图输出）

        Args:
            prompt: 编辑指令
            image_paths: 参考图路径列表
            output_dir: 输出目录
            max_images: 生成图片数量
            size: 输出尺寸
            watermark: 是否添加水印

        Returns:
            输出图片路径列表
        """
        print(f"\n{'='*60}")
        ref_names = ', '.join(str(p.name) if isinstance(p, Path) else str(p)[:30] for p in image_paths)
        print(f"🎨 图生组图 ({max_images}张): [{ref_names}] + \"{prompt[:40]}...\"")
        print(f"{'='*60}")

        urls = self.generate_image(
            prompt=prompt, images=image_paths, size=size, watermark=watermark,
            multi_image=True, max_images=max_images
        )

        paths = []
        for i, url in enumerate(urls):
            output_path = output_dir / f"image_{i+1}.png"
            self.download_image(url, output_path)
            paths.append(output_path)

        print(f"{'='*60}\n")
        return paths


# ============================================================================
# 辅助函数：用于快速测试
# ============================================================================

def test_api():
    """
    测试API是否正常工作

    使用方式:
        python3 tools/image/seedream_client.py
    """
    api_key = os.getenv('VOLCENGINE_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量: export VOLCENGINE_API_KEY=your_key")
        return

    print("🧪 测试 Seedream API...")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}\n")

    client = SeedreamClient(api_key=api_key)

    try:
        print("=" * 60)
        print("测试: 文生图")
        print("=" * 60)

        output_dir = Path('.')
        paths = client.text_to_image(
            prompt="写实风格，一杯拿铁咖啡放在木桌上，旁边有一本打开的书，温暖的午后阳光从窗户照进来，暖色调。",
            output_dir=output_dir,
            size="2K",
        )

        print(f"\n✅ 文生图测试成功!")
        for p in paths:
            print(f"   输出: {p}")

    except Exception as e:
        print(f"\n❌ 文生图测试失败: {e}")


if __name__ == '__main__':
    test_api()
