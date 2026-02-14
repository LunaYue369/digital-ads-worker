#!/usr/bin/env python3
"""
Minimal YouTube publisher.

Prerequisites:
- Create a Google Cloud project, enable YouTube Data API v3
- Download `client_secrets.json` (OAuth client) into working dir
- First-run: generates `token.json` via local browser auth

Usage: python tools/publish_youtube.py /path/to/video.mp4 --title "Title" --desc "Desc"
"""
import argparse
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_service():
    creds = None
    if os.path.exists('token.json'):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)


def upload(video_path, title, description, tags=None, privacy='public'):
    service = get_service()
    body = {
        'snippet': {'title': title, 'description': description, 'tags': tags or []},
        'status': {'privacyStatus': privacy}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    req = service.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    return resp


def main():
    p = argparse.ArgumentParser()
    p.add_argument('video')
    p.add_argument('--title', required=True)
    p.add_argument('--desc', required=True)
    p.add_argument('--tags', nargs='*')
    p.add_argument('--privacy', default='public')
    args = p.parse_args()
    resp = upload(args.video, args.title, args.desc, args.tags, args.privacy)
    print('Uploaded:', resp.get('id'))


if __name__ == '__main__':
    main()
