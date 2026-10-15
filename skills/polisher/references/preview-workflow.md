# Social preview workflow

## Establish deployment facts

Inspect Pages API/deployment records when available, configured custom domain (`CNAME` is read-only), workflow source/artifact paths, existing canonical/OG URLs and repository identity. Do not infer a successful deployment from a remote name alone. Reconcile conflicting URLs; if uncertain, skip URL-dependent writes and report why.

Standard candidates are `https://OWNER.github.io/` for `OWNER.github.io`, and `https://OWNER.github.io/REPO/` for a project site. Custom domains may replace these and project paths can differ. Verify the actual published URL. Build image URLs relative to the **site base directory**, preserving project prefix and escaping path segments. Avoid a leading `/assets/...` that loses `/REPO/`. Never use GitHub blob URLs, filesystem paths, localhost, private URLs or HTTP image URLs. Do not change canonical tags, redirects or base tags under this skill.

Eligible examples: static root `index.html`; `docs/index.html` when `/docs` is the published source; a source entry HTML copied by an existing Vite build with static metadata preserved. Jekyll/theme-generated heads, React/Next layouts and shared templates requiring non-entry changes are unsupported unless an existing editable entry HTML alone suffices. Frontmatter/template syntax in HTML must be preserved byte-for-byte. Never edit only discarded `dist` output, run in-place builds, add a plugin or change workflows to work around this boundary.

## Copy and image

Use actual functionality, visual identity and the site's language. Prefer a recognizable project title and one specific, concise description. Avoid fabricated claims, SEO keyword lists, hype, generic “powerful intuitive seamless” copy, automatic emoji and needless rewrites. Verify the current copy against source evidence; preserve it when adequate.

Prefer an existing suitable, publicly deployed raster image without modifying it. Otherwise create a new dedicated PNG/JPEG, preferably 1200 × 630 px, with readable short text, generous safe margins, contrast and project colors. Inspect at phone size if viewing tools exist. Do not crop/overwrite original assets. Preview images should not embed secrets, fabricated interface features or unlicensed third-party work.

If image generation is available, use that environment's supported image tool and preserve inputs. Do not assume desktop tools or external API keys exist. If it is absent, use an available raster renderer (for example Pillow with an available font) in scratch; otherwise reuse an existing suitable image. Avoid SVG as the final OG asset. If none is possible, report image generation unavailable; do not invent a file, URL or claim of success. Do not install packages, alter manifests or add a renderer to the target repo.

New generated files should use an unoccupied dedicated name such as `assets/social/polisher-<content-sha256-prefix>.png` under the existing deployment asset mapping. Never overwrite a preexisting file based on its name alone. Later updates may create another dedicated image and update metadata, leaving the old file untouched. Updating an existing image requires reliable history evidence of polisher ownership and exclusive preview usage; prefer new content-addressed names. Reuse the same existing image when adequate. Do not create empty directories or extra assets when no image will be produced.

## Metadata

Patch only static metadata tags in an existing `<head>`, preserving all other bytes. Use HTML attribute escaping, not string interpolation of unescaped title/URL. Consolidate duplicate/conflicting **supported** OG/Twitter keys to one per key. Preserve unrelated metadata, `<title>`, canonical, styles, scripts, body and formatting. For multi-image galleries or structured OG data, understand existing groups; do not casually flatten semantic groups. If eliminating a conflict needs changing an unsupported tag or template/config, skip and explain.

Required when facts/image are available:

```html
<meta property="og:type" content="website">
<meta property="og:title" content="PROJECT TITLE">
<meta property="og:description" content="TRUTHFUL DESCRIPTION">
<meta property="og:url" content="https://OWNER.github.io/REPO/">
<meta property="og:image" content="https://OWNER.github.io/REPO/assets/social/IMAGE.png">
<meta name="twitter:card" content="summary_large_image">
```

Useful supported keys: `og:site_name`, `og:locale`, `og:image:secure_url`, `og:image:type`, `og:image:width`, `og:image:height`, `og:image:alt`, `twitter:title`, `twitter:description`, `twitter:image`, `twitter:image:alt`. Only declare actual dimensions/type. If a previously owned stale image key cannot be corrected truthfully, remove that supported key instead of inventing facts. A standard `name="description"` may be edited only when directly needed to resolve the sharing-description behavior, with no unrelated SEO work.

Some crawlers ignore client-side DOM updates. Confirm the initial server HTML contains the values and image path in the actual deployed artifact; a source file alone is only local verification. When building is needed to inspect output, use an isolated temporary copy with root README excluded, no dependency installation and no writes back; if this cannot run within the constraints, report build verification unavailable.

## Checks and report

- Verify exact allowed paths; HTML mutations only supported metadata inside head; no deletions/renames, original asset edits or user changes overwritten. Guard success does not prove semantic correctness or a deployed artifact.
- Check each managed key is unique, has correct escaping, and uses the confirmed site URL/path; ensure JS is not required to produce tags.
- Confirm the image is real PNG/JPEG of stated dimensions, part of existing deploy mapping, legible and reachable over public HTTPS if live checks are possible. A 200 response containing an HTML error page is not an image.
- If network is available, GET the live Pages HTML without client JS and GET the image, checking status, content type, decoded raster dimensions and final redirected URLs. Record whether fetched values match the proposed changes. Never deploy or trigger external cache refresh tools without separate user authorization.
- Distinguish “本地檢查通過”, “已驗證線上 HTML／圖片” and “平台快取未驗證”. Do not claim Messenger preview updated based on local edits or HTTP checks. Explain that the owner must publish/merge through the existing process and social platforms may cache old cards.

Sources: [Open Graph protocol](https://ogp.me/), [GitHub Pages custom domains](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages), [Codex Cloud](https://learn.chatgpt.com/docs/environments/cloud-environments).
