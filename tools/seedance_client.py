#!/usr/bin/env python3
"""
Seedance 1.0 Pro Fast API Client for Video Generation
火山引擎 Seedance 视频生成客户端

Based on official API documentation:
https://www.volcengine.com/docs/82379/1520757
"""
import os
import time
import json
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class SeedanceClient:
    """
    火山引擎 Seedance 视频生成API客户端

    使用方式:
        client = SeedanceClient(api_key=os.getenv('VOLCENGINE_API_KEY'))
        video_path = client.generate_video_from_image(
            image_path='path/to/image.jpg',
            prompt='产品特写镜头，缓慢旋转展示细节',
            duration=3,
            output_path='output.mp4'
        )
    """

    # 火山引擎官方API地址（基于文档）
    BASE_URL = "https://ark.cn-beijing.volces.com"
    CREATE_ENDPOINT = "/api/v3/contents/generations/tasks"
    QUERY_ENDPOINT = "/api/v3/contents/generations/tasks"  # GET /{id}

    # 模型从 .env 的 SEEDANCE_MODEL 读取

    def __init__(
        self,
        api_key: str,
        model: str = None,
        default_resolution: str = None,
        default_ratio: str = None
    ):
        """
        初始化客户端

        Args:
            api_key: 火山引擎API密钥
            model: 模型ID (默认从.env读取SEEDANCE_MODEL)
            default_resolution: 默认分辨率 (默认从.env读取DEFAULT_RESOLUTION)
            default_ratio: 默认宽高比 (默认从.env读取DEFAULT_RATIO)
        """
        self.api_key = api_key
        self.model = model or os.getenv('SEEDANCE_MODEL')
        if not self.model:
            raise ValueError("未配置模型，请在 .env 中设置 SEEDANCE_MODEL")
        self.default_resolution = default_resolution or os.getenv('DEFAULT_RESOLUTION', '720p')
        self.default_ratio = default_ratio or os.getenv('DEFAULT_RATIO', '16:9')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def _encode_image_base64(self, image_path: Path) -> str:
        """
        将图片编码为base64字符串

        Args:
            image_path: 图片文件路径

        Returns:
            base64编码的图片字符串
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')

    def create_video_task(
        self,
        content: list,
        duration: int = 5,
        resolution: str = None,
        ratio: str = None,
        watermark: bool = False,
        seed: int = -1
    ) -> str:
        """
        创建视频生成任务（异步）

        Args:
            content: 内容列表，支持以下格式：
                     [{"type": "text", "text": "提示词"}]
                     [{"type": "image", "image": "base64_encoded_image"}]
                     [{"type": "text", "text": "..."}, {"type": "image", "image": "..."}]
            duration: 视频时长（秒），支持2-12秒
            resolution: 视频分辨率 (480p/720p/1080p)
            ratio: 宽高比 (16:9/4:3/1:1/3:4/9:16/21:9)
            watermark: 是否添加水印
            seed: 随机种子 (-1表示随机)

        Returns:
            task_id: 任务唯一ID

        Raises:
            Exception: API调用失败
        """
        payload = {
            "model": self.model,
            "content": content,
            "duration": duration,
            "resolution": resolution or self.default_resolution,
            "ratio": ratio or self.default_ratio,
            "watermark": watermark,
            "seed": seed
        }

        print(f"📤 创建视频生成任务...")
        print(f"   模型: {self.model}")
        print(f"   时长: {duration}秒")
        print(f"   分辨率: {payload['resolution']}, 宽高比: {payload['ratio']}")

        try:
            response = self.session.post(
                f"{self.BASE_URL}{self.CREATE_ENDPOINT}",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            task_id = result.get('id')

            if not task_id:
                raise ValueError(f"API返回格式错误，未找到id字段: {result}")

            print(f"✅ 任务已创建: {task_id}")
            return task_id

        except requests.exceptions.RequestException as e:
            print(f"❌ API调用失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   状态码: {e.response.status_code}")
                print(f"   响应内容: {e.response.text}")
            raise

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务详情字典，格式：
            {
                "id": "cgt-xxx",
                "status": "queued/running/succeeded/failed/expired/cancelled",
                "content": {"video_url": "https://..."},
                "created_at": 1743414619,
                "updated_at": 1743414673,
                "seed": 10,
                "resolution": "720p",
                "ratio": "16:9",
                "duration": 5,
                "framespersecond": 24,
                ...
            }
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}{self.QUERY_ENDPOINT}/{task_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ 查询任务状态失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   响应: {e.response.text}")
            raise

    def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> str:
        """
        等待任务完成（轮询）

        Args:
            task_id: 任务ID
            timeout: 最大等待时间（秒），默认5分钟
            poll_interval: 轮询间隔（秒），默认5秒

        Returns:
            video_url: 生成视频的下载链接

        Raises:
            TimeoutError: 超时
            Exception: 任务失败
        """
        start_time = time.time()
        last_status = None

        print(f"⏳ 等待任务完成 (最多{timeout}秒)...")

        while True:
            elapsed = time.time() - start_time

            # 检查超时
            if elapsed > timeout:
                raise TimeoutError(
                    f"任务 {task_id} 超时 ({timeout}秒)，最后状态: {last_status}"
                )

            # 查询状态
            result = self.query_task_status(task_id)
            status = result.get('status', 'unknown')

            # 状态变化时打印
            if status != last_status:
                elapsed_str = f"{int(elapsed)}秒"
                print(f"   状态: {status} (已等待 {elapsed_str})")
                last_status = status

            # 成功：返回视频URL
            if status == 'succeeded':
                content = result.get('content', {})
                video_url = content.get('video_url')

                if not video_url:
                    raise ValueError(f"任务成功但未返回video_url: {result}")

                print(f"✅ 视频生成完成!")
                print(f"   URL: {video_url}")
                return video_url

            # 失败：抛出异常
            if status in ['failed', 'expired', 'cancelled']:
                error = result.get('error', {})
                error_msg = error.get('message', 'Unknown error')
                raise Exception(f"任务失败 (status={status}): {error_msg}")

            # 继续等待
            time.sleep(poll_interval)

    def download_video(self, video_url: str, output_path: Path):
        """
        下载生成的视频

        Args:
            video_url: 视频下载链接
            output_path: 保存路径
        """
        print(f"📥 下载视频: {output_path.name}")

        try:
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            print(f"✅ 下载完成: {file_size:.2f} MB")

        except requests.exceptions.RequestException as e:
            print(f"❌ 下载失败: {e}")
            raise

    # ========================================================================
    # 便捷方法：一步到位的视频生成
    # ========================================================================

    def generate_video_from_image(
        self,
        image_path: Path,
        prompt: str,
        output_path: Path,
        duration: int = 3,
        resolution: str = None,
        ratio: str = None,
        timeout: int = 300
    ) -> Path:
        """
        从图片生成视频（图生视频 i2v）

        这是一个便捷方法，包含创建任务、等待完成、下载视频的完整流程

        Args:
            image_path: 输入图片路径
            prompt: 视频生成提示词（描述运动方式）
            output_path: 输出视频路径
            duration: 视频时长（秒），2-12秒
            resolution: 分辨率 (默认使用初始化时的设置)
            ratio: 宽高比 (默认使用初始化时的设置)
            timeout: 最大等待时间（秒）

        Returns:
            输出视频的路径

        Example:
            client = SeedanceClient(api_key="xxx")
            video_path = client.generate_video_from_image(
                image_path=Path('product.jpg'),
                prompt='产品360度旋转展示，匀速运动',
                output_path=Path('shot1.mp4'),
                duration=3
            )
        """
        print(f"\n{'='*60}")
        print(f"🎬 图生视频: {image_path.name} → {output_path.name}")
        print(f"{'='*60}")

        # 1. 编码图片
        image_base64 = self._encode_image_base64(image_path)

        # 2. 创建任务
        content = [
            {"type": "text", "text": prompt},
            {"type": "image", "image": image_base64}
        ]

        task_id = self.create_video_task(
            content=content,
            duration=duration,
            resolution=resolution,
            ratio=ratio,
            watermark=False
        )

        # 3. 等待完成
        video_url = self.wait_for_completion(
            task_id=task_id,
            timeout=timeout
        )

        # 4. 下载视频
        self.download_video(video_url, output_path)

        print(f"{'='*60}\n")
        return output_path

    def generate_video_from_text(
        self,
        prompt: str,
        output_path: Path,
        duration: int = 5,
        resolution: str = None,
        ratio: str = None,
        watermark: bool = False,
        timeout: int = 300
    ) -> Path:
        """
        从文本生成视频（文生视频 t2v

        Args:
            prompt: 视频生成提示词
            output_path: 输出视频路径
            duration: 视频时长（秒），2-12秒
            resolution: 分辨率
            ratio: 宽高比
            watermark: 是否添加水印
            timeout: 最大等待时间（秒）

        Returns:
            输出视频的路径

        Example:
            client = SeedanceClient(api_key="xxx")
            video_path = client.generate_video_from_text(
                prompt='一只猫对着镜头打哈欠',
                output_path=Path('cat_yawn.mp4'),
                duration=5
            )
        """
        print(f"\n{'='*60}")
        print(f"🎬 文生视频: {prompt[:50]}...")
        print(f"{'='*60}")

        # 1. 创建任务
        content = [{"type": "text", "text": prompt}]

        task_id = self.create_video_task(
            content=content,
            duration=duration,
            resolution=resolution,
            ratio=ratio,
            watermark=watermark
        )

        # 2. 等待完成
        video_url = self.wait_for_completion(
            task_id=task_id,
            timeout=timeout
        )

        # 3. 下载视频
        self.download_video(video_url, output_path)

        print(f"{'='*60}\n")
        return output_path


# ============================================================================
# 辅助函数：用于快速测试
# ============================================================================

def test_api():
    """
    测试API是否正常工作

    使用方式:
        export VOLCENGINE_API_KEY=your_key
        python3 seedance_client.py
    """
    api_key = os.getenv('VOLCENGINE_API_KEY')
    if not api_key:
        print("❌ 请设置环境变量: export VOLCENGINE_API_KEY=your_key")
        return

    print("🧪 测试 Seedance API...")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}\n")

    client = SeedanceClient(api_key=api_key)

    # 测试文生视频
    try:
        print("=" * 60)
        print("测试1: 文生视频")
        print("=" * 60)

        output = client.generate_video_from_text(
            prompt="写实风格，晴朗的蓝天之下，一大片白色的雏菊花田，镜头逐渐拉近",
            output_path=Path('test_text_to_video.mp4'),
            duration=3,
            timeout=300
        )

        print(f"\n✅ 文生视频测试成功！")
        print(f"   输出: {output}\n")

    except Exception as e:
        print(f"\n❌ 文生视频测试失败: {e}\n")

    # 测试图生视频（如果有测试图片）
    test_image = Path('test_input.jpg')
    if test_image.exists():
        try:
            print("=" * 60)
            print("测试2: 图生视频")
            print("=" * 60)

            output = client.generate_video_from_image(
                image_path=test_image,
                prompt="产品360度旋转展示，匀速运动，突出细节",
                output_path=Path('test_image_to_video.mp4'),
                duration=3,
                timeout=300
            )

            print(f"\n✅ 图生视频测试成功！")
            print(f"   输出: {output}\n")

        except Exception as e:
            print(f"\n❌ 图生视频测试失败: {e}\n")
    else:
        print(f"ℹ️  跳过图生视频测试（未找到测试图片: {test_image}）\n")


if __name__ == '__main__':
    test_api()
