# Guard usage and limits

Resolve the installed skill location from the current skill catalog, and the target root from Git. Use the available Python 3 executable. These commands are illustrative placeholders, not literal paths to create:

```text
python3 <skill>/scripts/polisher_guard.py snapshot --root <repo> --out <outside-temp>/baseline.json
python3 <skill>/scripts/polisher_guard.py verify --root <repo> --baseline <outside-temp>/baseline.json --html docs/index.html --image docs/assets/social/polisher-HASH.png
python3 <skill>/scripts/polisher_guard.py head-check --before <outside-temp>/original-index.html --after <repo>/docs/index.html
```

Repeat `--html`/`--image` for each exact allowed path; omit image options when reusing an unchanged asset. Before modifying each eligible HTML, save its original bytes outside the repo. Never create/replace/delete entry HTML as a fallback. Snapshot output uses exclusive creation to avoid overwriting a previous baseline.

`verify` compares all non-README regular file bytes/modes and symlink identities, including ignored and untracked files. It rejects deleted files, writes outside the exact allowlist, new entry HTML, symlink writes, changed file permissions, existing image overwrites and images without PNG/JPEG signatures. It does not follow links, and refuses hardlinked files and nested repositories. Missing/unreadable files cause failure. It deliberately excludes the root README (case-insensitive) without stat/open/hash, so it cannot enforce the README rule. Handle first-pass README preimage/dirty checks and validation only within that pass.

`head-check` compares original and edited UTF-8 HTML after removing only supported metadata tag spans inside one explicit head. Every remaining character must be identical, including whitespace. Insert tags immediately adjacent to an existing tag or `</head>` without adding whitespace outside the new tags. This is deliberately strict; if it fails, narrow the patch instead of reformatting or weakening the audit. It rejects duplicate managed keys in the result and ambiguous attributes. It does not render templates or prove a build will preserve tags.

These are verification helpers, not a transaction manager or security sandbox. They do not decide which HTML deploys, establish image ownership, decode images, validate crawler behavior, prevent concurrent writes, detect all races or establish a correct Pages URL. A PNG/JPEG signature is not proof of a valid image; decode it with an available image tool and verify dimensions separately. An allowed path alone is insufficient: every HTML change also needs `head-check`, and every proposed write needs a clean preimage checked immediately beforehand. Do not overwrite user changes even when their path is in the allowlist.

Use read-only Git status/diffs with an explicit root README exclusion on follow-ups. During first pass, preexisting staged/unstaged/untracked edits to README or a prospective metadata/image target make that operation ineligible. The baseline preserves existing unrelated dirty work but is not proof that a permitted file was clean. In a concurrent task, a new out-of-scope change might belong to another actor: report failure and inspect only relevant non-README paths; never revert, delete or overwrite another actor's work to make the audit pass.

No helper writes source files or stores persistent state. If the audit cannot run, perform equivalent narrow inspection and state the limitation; do not label it a guard pass. Keep temporary data outside the target repo and do not commit it. Final verification must not reopen README after the one-time operation is declared complete.
