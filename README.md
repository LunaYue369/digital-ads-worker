# Digital Ads Worker

AI-powered ad creative toolkit and business analytics dashboard. Generates marketing images and videos using Volcengine's Seedream/Seedance models, publishes to Reddit and YouTube, and provides a real-time POS analytics dashboard.

## Features

- **AI Image Generation** -- Text-to-image, image-to-image, multi-reference fusion, and batch generation via Seedream 4.5 (supports 2K/4K resolution)
- **AI Video Generation** -- Text-to-video and image-to-video via Seedance 1.5 Pro with audio synchronization (dialogue, SFX, BGM)
- **Reddit Publishing** -- Automated media and text post publishing via Playwright browser automation with persistent login
- **YouTube Publishing** -- Upload and publish videos via YouTube Data API v3
- **Business Dashboard** -- Streamlit-based POS analytics with live KPIs, hourly sales charts, top items, category breakdowns, and payment method tracking (auto-refreshes every 10s)

## Architecture

```
tools/
  image/
    make_ad_image.py        # CLI: generate ad images
    seedream_client.py      # Volcengine Seedream 4.5 API client
  video/
    make_ad_video.py        # CLI: generate ad videos with audio sync
    seedance_client.py      # Volcengine Seedance 1.5 Pro API client
  reddit/
    publish_reddit.py       # Playwright-based Reddit publisher
  youtube/
    publish_youtube.py      # YouTube Data API uploader
dashboard/
  app.py                    # Streamlit POS analytics dashboard
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Image Generation | Volcengine Seedream 4.5 |
| Video Generation | Volcengine Seedance 1.5 Pro |
| Browser Automation | Playwright |
| Dashboard | Streamlit, Plotly |
| Data Storage | SQLite |
| Video API | YouTube Data API v3 |

## Quick Start

```bash
pip install -r requirements.txt

# Generate an ad image
python tools/image/make_ad_image.py --prompt "Fresh sushi platter, premium restaurant"

# Generate a video
python tools/video/make_ad_video.py data/media/<run_id>

# Launch the dashboard
streamlit run dashboard/app.py
```

## Dashboard Preview

The analytics dashboard features a Square-inspired UI with:
- Revenue, orders, covers, and average check KPIs with period-over-period comparison
- Interactive Plotly charts (hourly sales, daily trends, category donut)
- Live catalog view and recent transactions table
- Multi-industry support (restaurant, spa, auto dealer)
