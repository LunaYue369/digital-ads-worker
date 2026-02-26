#!/usr/bin/env python3
"""
YouTube Data API v3 Client for Video Upload
YouTube 视频上传客户端

Usage:
    client = YouTubeClient(client_secret_path='client_secret.json')
    video_id, url = client.upload_video(
        video_path=Path('video.mp4'),
        title='My Video',
        description='Video description',
    )
"""
import os
import pickle
from pathlib import Path
from typing import Optional, List, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


class YouTubeClient:
    """
    YouTube 视频上传客户端

    首次使用时会打开浏览器进行 OAuth 授权，之后自动使用保存的 token。
    """

    def __init__(
        self,
        client_secret_path: str = None,
        token_path: str = None,
    ):
        """
        初始化客户端

        Args:
            client_secret_path: OAuth client_secret.json 文件路径
            token_path: token.pickle 保存路径
        """
        root = Path(__file__).parent.parent.parent
        self.client_secret_path = Path(client_secret_path or root / 'client_secret.json')
        self.token_path = Path(token_path or root / 'token.pickle')

        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"找不到 {self.client_secret_path}\n"
                "请从 Google Cloud Console 下载 OAuth 凭证并保存为 client_secret.json"
            )

        self.youtube = self._authenticate()

    def _authenticate(self):
        """
        OAuth 2.0 认证

        首次运行: 打开浏览器授权，保存 token.pickle
        后续运行: 加载 token.pickle，自动刷新过期 token
        """
        creds = None

        if self.token_path.exists():
            with open(self.token_path, 'rb') as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 刷新 YouTube access token...")
                creds.refresh(Request())
            else:
                print("🌐 首次授权：正在打开浏览器...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secret_path),
                    SCOPES
                )
                creds = flow.run_local_server(port=8090)
                print("✅ 授权成功!")

            with open(self.token_path, 'wb') as f:
                pickle.dump(creds, f)

        return build('youtube', 'v3', credentials=creds)

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str = '',
        tags: Optional[List[str]] = None,
        privacy: str = 'private',
        category: str = '22',
    ) -> Tuple[str, str]:
        """
        上传视频到 YouTube

        Args:
            video_path: 视频文件路径
            title: 视频标题
            description: 视频描述
            tags: 标签列表
            privacy: 隐私级别 (private/unlisted/public)
            category: YouTube 分类 ID (默认22=People & Blogs)

        Returns:
            (video_id, video_url) 元组
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        file_size = video_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"📤 YouTube 视频上传")
        print(f"{'='*60}")
        print(f"📹 文件: {video_path.name} ({file_size:.1f} MB)")
        print(f"📝 标题: {title}")
        print(f"🔒 隐私: {privacy}")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or [],
                'categoryId': category,
            },
            'status': {
                'privacyStatus': privacy,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype='video/mp4',
            resumable=True,
        )

        request = self.youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media,
        )

        print(f"\n🚀 开始上传...")

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"   上传进度: {progress}%")

        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        print(f"\n{'='*60}")
        print(f"✅ 上传成功!")
        print(f"🆔 Video ID: {video_id}")
        print(f"🔗 URL: {video_url}")
        print(f"{'='*60}\n")

        return video_id, video_url
