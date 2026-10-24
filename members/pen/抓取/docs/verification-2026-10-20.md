# Verification — 2026-10-20

## Provenance and package

The original source was exported from the existing Omni Scraper Grok Bot. Export ZIP SHA-256: `287701e93b03106365947b6d76266994f4505916c5599e24cd825f1b638ad26e` (47,995 bytes, 32 files). The existing Bot reports that its original directory remains present and has no Git repository or remote.

The Python implementation is retained unchanged. Packaging adds a root Agent Plugins manifest and a discoverable `skills/omniscraper/SKILL.md`, replaces the environment-specific entry instructions, and separates minimal installation from optional dependencies. Original instructions and historical reports are preserved and labelled as such.

No credentials, virtual environment, collected output or third-party binaries are part of this source package. A credential-pattern scan of the export found no private-key header or token-shaped API/GitHub credential; this is a limited scan, not a security certification.

## Local real-world smoke tests

Environment: macOS, Python 3.12.11, requests 2.34.2, yt-dlp 2026.8.19. Fresh virtual environment. `BEATAPI_API_KEY` and `BEATAPI_BASE` were explicitly removed from each process environment. No `--fallback-beatapi`, media or transcription flags were used.

| Case | Public input | Observed result |
| --- | --- | --- |
| Bluesky | https://bsky.app/profile/bsky.app/post/3l6oveex3ii2l | Exit 0; text, author, four engagement-field names and 50 comments returned. `needs_beatapi` empty. Markdown and JSON created. |
| X | https://x.com/elonmusk/status/1585341984679469056 | Exit 0; text, author, likes/replies and an image URL returned. Comments not returned; `needs_beatapi` lists comments and the CLI printed the optional paid fallback instructions. No paid call occurred. Markdown and JSON created. |

Python syntax compilation passed for all included Python source. These two samples establish a limited smoke test only; they do not verify all platform modules, media extraction, transcription or any paid fallback mapping. Full raw collected outputs remain outside the public source package.

## Grok Bot environment

The existing native Bot was asked, with user authorization, to inspect its original source, export a clean ZIP and run free tests. Its original-source ZIP was received and independently inspected. The report was received and checked. It reports free tests in the native Grok Bot Linux environment on 2026-10-20 from 21:57 to 22:07 Asia/Shanghai. YouTube (https://www.youtube.com/watch?v=jNQXAC9IVRw) returned title, author, description, metadata and 20 comments. Reddit returned archived data via arctic-shift after live access was blocked; the source URL path in that test had the wrong subreddit, so treat it only as an archive-adapter check. The wider regression was stopped without field-by-field acceptance; its process exit codes are not a platform success rate. Douyin and Xiaohongshu were restricted, TikTok comments were empty, and the optional Pinterest CLI path was incompatible with that environment. No paid call or personal account/cookie was used. This is a report from the existing Bot, with independent local source tests listed above.

The newly assembled Agent Plugin has not been installed from a public Marketplace listing. No Marketplace approval, recommendation or install availability is claimed.
