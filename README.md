# social_poster

Automated pipeline for an AI influencer account: watches a Google Drive folder
for new videos, uses Claude to write a caption/hashtags and pick a music mood,
burns in a text overlay and mixes in background music with ffmpeg, then
publishes the result to Instagram Reels and TikTok. Runs on a schedule via
GitHub Actions -- no manual posting.

```
Drive folder (raw videos)
        |
        v
  download new video  --------------------------+
        |                                        |
        v                                        |
  Claude analyzes sampled frames                  |
  -> caption, hashtags, overlay text, mood        |
        |                                         |
        v                                         |
  pick a track from music_library/ for that mood  |
        |                                         |
        v                                         |
  ffmpeg: burn in overlay text + mix in music -> processed video
        |
        +--> upload to Drive (public link) --> Instagram Graph API (Reels)
        |
        +--> direct chunked upload --> TikTok Content Posting API
        |
        v
  mark the source Drive file as posted (so it's never reposted)
```

## 1. Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . -r requirements-dev.txt
sudo apt-get install ffmpeg   # or brew install ffmpeg on macOS
cp .env.example .env          # fill in the values from the sections below
```

Add your own royalty-free music (see [Music library](#5-music-library) below), then:

```bash
python -m social_poster.cli --dry-run -v   # renders a video, doesn't publish
python -m social_poster.cli -v             # actually posts
```

## 2. Google Drive setup (source of videos)

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Google Drive API**.
2. Create a **Service Account** (IAM & Admin -> Service Accounts), then create a JSON key for it and download it.
3. In Google Drive, create two folders: one you'll drop raw videos into, and one the tool will use for processed/public copies (needed so Instagram's servers can fetch the rendered video by URL).
4. Share **both** folders with the service account's email address (looks like `xxx@yyy.iam.gserviceaccount.com`, found in the JSON key) as **Editor**.
5. Grab each folder's ID from its URL: `https://drive.google.com/drive/folders/<THIS_PART>`.
6. Base64-encode the JSON key and put it in `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`:
   ```bash
   base64 -w0 service-account.json
   ```

Videos are matched by MIME type (anything under `video/`), so any format Drive recognizes as video works; ffmpeg needs to be able to decode it too (mp4/mov are safest).

## 3. Instagram setup (Meta Graph API)

Requires an Instagram **Business or Creator** account linked to a Facebook Page.

1. Convert your Instagram account to Business/Creator in the Instagram app (Settings -> Account type) if it isn't already, and link it to a Facebook Page.
2. Create an app at [developers.facebook.com](https://developers.facebook.com/apps) and add the **Instagram Graph API** product.
3. In [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your app, generate a User Access Token with `instagram_basic`, `instagram_content_publish`, and `pages_show_list` permissions.
4. Exchange it for a long-lived token (60 days, needs manual/periodic renewal):
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
       ?grant_type=fb_exchange_token
       &client_id={app-id}&client_secret={app-secret}
       &fb_exchange_token={short-lived-token}
   ```
5. Find your Page, then your IG Business Account ID:
   ```
   GET /me/accounts                                    -> page id
   GET /{page-id}?fields=instagram_business_account     -> IG business account id
   ```
6. Set `IG_ACCESS_TOKEN` (the long-lived token) and `IG_BUSINESS_ACCOUNT_ID`.

Instagram's Reels API requires a **publicly fetchable URL** for the video (not a direct file upload), which is why the pipeline re-uploads the processed video to your Drive "processed" folder with link sharing on and passes that URL along.

## 4. TikTok setup (Content Posting API)

1. Create an app at the [TikTok Developer Portal](https://developers.tiktok.com/), add the **Content Posting API** product.
2. Complete TikTok's app review/audit for the `video.publish` scope. **Until it's approved, posts are forced private (`SELF_ONLY`)** -- you'll still see them land on your own account, just not publicly, which is fine for testing the pipeline end to end.
3. Run TikTok's OAuth flow once (authorization code -> token exchange) to get a `refresh_token` for your own account. TikTok's docs walk through this; any small script hitting `https://www.tiktok.com/v2/auth/authorize/` then `https://open.tiktokapis.com/v2/oauth/token/` works.
4. Set `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`. The tool mints a fresh access token from these on every run (access tokens only last ~24h, so this is the path that actually works unattended).
5. **Known limitation:** TikTok rotates the refresh token every time it's used. If auth starts failing after the pipeline has run a few times, check the Action logs for a line like `TikTok rotated the refresh token. Update the TIKTOK_REFRESH_TOKEN secret to: ...` and update the `TIKTOK_REFRESH_TOKEN` GitHub secret to that value. Once your app is audited you may be able to move to a longer-lived integration; until then this is a periodic manual step (roughly whenever you notice a failure, refresh tokens are valid ~1 year of inactivity but rotate on use).
6. Once TikTok approves your audit, set `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE`.

## 5. Music library

You need to supply your own royalty-free tracks -- this repo doesn't ship any (licensing).

1. `cp music_library/library.example.json music_library/library.json`
2. Download tracks you have the rights to use for each mood from a royalty-free source, e.g.:
   - [YouTube Audio Library](https://studio.youtube.com/channel/UC/music) (free, no attribution required for most tracks)
   - [Pixabay Music](https://pixabay.com/music/)
   - [Free Music Archive](https://freemusicarchive.org/)
3. Drop the mp3 files in `music_library/`, and reference them in `library.json` under the matching mood (`energetic`, `chill`, `uplifting`, `dramatic`, `funny`, `romantic`, `mysterious`, `inspirational`). Multiple tracks per mood are fine -- one is picked at random each run.
4. `library.json` and the mp3s are gitignored so you don't accidentally commit copyrighted audio -- for GitHub Actions, commit them anyway if you've confirmed you have the rights to redistribute them (see [`.gitignore`](.gitignore)), or adjust the workflow to fetch them from private storage instead.

Claude picks a `mood` for each video from that same fixed list, so whatever you stock each bucket with should broadly match the vibe implied by its name.

## 6. Running on a schedule (GitHub Actions)

`.github/workflows/post_videos.yml` runs every 3 hours by default and posts at
most `MAX_VIDEOS_PER_RUN` videos per run (default 1) -- together those two
settings are your posting cadence. Add these as **repository secrets**
(Settings -> Secrets and variables -> Actions) using the same names as in
`.env.example`:

- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`, `DRIVE_SOURCE_FOLDER_ID`, `DRIVE_PROCESSED_FOLDER_ID`
- `ANTHROPIC_API_KEY`
- `ENABLE_INSTAGRAM`, `IG_BUSINESS_ACCOUNT_ID`, `IG_ACCESS_TOKEN`
- `ENABLE_TIKTOK`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`, `TIKTOK_PRIVACY_LEVEL`
- `MAX_VIDEOS_PER_RUN` (optional, defaults to 1)

You can also trigger a run manually from the Actions tab (`workflow_dispatch`), optionally as a dry run.

## 7. How "already posted" is tracked

No database needed: after a successful publish, the tool writes
`appProperties` (`posted=true`, `posted_at`, `posted_instagram`,
`posted_tiktok`) onto the **source** Drive file itself. Each run only looks at
files without `posted=true`. If a platform publish fails, the video is left
unmarked so it's retried on the next scheduled run.

## Project layout

```
src/social_poster/
  config.py          settings from env vars
  drive_client.py     list/download/upload/mark-processed against Drive
  content_analysis.py frame sampling + Claude call -> caption/hashtags/mood
  music_library.py    mood -> track selection
  video_editor.py      ffmpeg text overlay + music mixing
  publishers/
    instagram.py       Graph API Reels container create/poll/publish
    tiktok.py           Content Posting API chunked upload + publish
  pipeline.py           orchestrates the above end to end
  cli.py                entry point (python -m social_poster.cli)
tests/                  unit tests for the pure logic (music selection, text wrapping, JSON parsing)
.github/workflows/post_videos.yml   scheduled + manual GitHub Action
```
