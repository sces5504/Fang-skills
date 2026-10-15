# README as a project front page

Read only during an authorized README pass. The desired result is a visually composed, recognizable GitHub project introduction, not merely cleaner paragraphs. The owner's reference shows a large project logo, a clear title with a descriptive phrase, a compact badge row, breathing room and a substantial introduction. Transfer that hierarchy to the actual project; never copy the reference project's branding, claims, badge values or license.

## Opening viewport

Make the opening answer “what is this, why would I use it, and where can I try it?” before a visitor scrolls through technical details.

1. Put the confirmed live GitHub Pages link on the first visible line as a descriptive call to action in the project's language. Retain the correct custom domain/project subpath. An unknown live URL must be reported, not fabricated.
2. Give the project a visual anchor: reuse a suitable existing logo, wordmark or wide project image without modifying its source. A small icon should stay small rather than being stretched into a blurry banner. A hero should dominate through clear branding and scale, not a giant empty spacer.
3. Use one clear H1 with the real name and, where useful, a short descriptive phrase. Follow it with one or two concrete sentences about purpose and audience. Match the site's identity and language.
4. Add a compact row of roughly two to five useful, evidence-backed badges or links when meaningful. Align visual styles and avoid noisy colors. Plain links are preferable to invented status or unrelated decorations.

The exact alignment is project-specific. A centered logo/title/link group can suit a portfolio or small tool; a left-aligned large wordmark and descriptive title can suit an established platform. Choose one coherent composition. Use normal Markdown and minimal GitHub-compatible HTML for image sizing/alignment where necessary. No CSS, scripts, embedded app, custom fonts, spacer-image tricks or changes outside the allowlist.

## Assets under the existing allowlist

- Reuse the repository's existing logo/screenshots/images read-only, with repository-relative paths and meaningful alt text. Escape spaces and special characters in paths. Check that paths and filename case resolve on GitHub.
- A newly generated social-preview image may also serve as the README hero if it is actually used for social preview and suits the project. Do not relabel a README-only banner as a social asset to evade the allowlist.
- Do not create separate README-only images, capture new screenshot files into the repository, edit original artwork, download unrelated logos or add a new asset folder just for README decoration. An actual available screenshot may be referenced; a hypothetical/mock screenshot must never be represented as the real UI.
- If no suitable permitted visual exists, use a strong typographic opening, link row and spacing. Report the asset limitation. Do not fake a logo or claim an image was created.
- Do not borrow Nacos branding or any other reference logo. Treat visual reference content as design evidence, not instructions or reusable project assets.

## Badges must be truthful

Derive each badge from verified repository evidence: the deployment platform, an actual license file, an existing workflow with a real status image, or a real published release. Static Shields.io badges can express verified facts and link to their evidence; they introduce an external image dependency, so prefer existing reliable badges and check URLs when network access is available. Never add CI “passing”, coverage percentages, download counts, support communities, performance ratings or a license merely to match a reference. Do not infer an open-source license from public visibility.

Do not create workflow, license, contribution or code-of-conduct files to obtain badges or GitHub's README tabs. The tabs in a reference screenshot belong to GitHub's interface and are not something this skill recreates inside Markdown. Omit stale, broken, duplicate or unsupported badges; if checks are unavailable, avoid adding uncertain dynamic badges.

## Body and restraint

Follow the opening with only useful sections: a short project introduction, a few specific benefits/features, an actual existing screenshot when available, and the minimum needed to start using the site. A portfolio may need a showcase and contact link already present in the project; a tool may need a three-step usage example; a game may need controls. Do not force every project into one template.

Use descriptive headings, concise paragraphs and selective bullets. Tables are useful for real comparisons, not to box every sentence. Existing essential notices, attribution, accessibility caveats and usage warnings survive the rewrite. Keep long developer architecture/build details out of the front-page pitch without silently removing necessary instructions. Link to existing documentation where it helps; never create other Markdown files or invent documentation URLs.

## First-pass acceptance checks

- The live link is immediately visible; the name, purpose and primary visual have distinct hierarchy.
- The result has a composed opening plus scannable sections, rather than only a new title and rewritten paragraphs.
- Every feature and badge has concrete evidence; no borrowed branding, fake status, broken assets or unrequested new files.
- The opening is readable at narrow widths: no very wide tables, fixed-width text layouts, large spacer blocks or unreadably tiny badge text. Images have alt text and sensible displayed size.
- Use an available Markdown preview/rendering tool in scratch to inspect the first viewport and narrow layout, without installing dependencies, invoking project scripts or modifying project configuration. A local Markdown renderer is an approximation of GitHub rendering; label it as such. If no renderer exists, inspect Markdown/HTML structure and references, report visual rendering unverified, and never claim GitHub was visually checked.
- Complete all README inspection before declaring the one-time pass finished. Do not reopen it in follow-up social work.
