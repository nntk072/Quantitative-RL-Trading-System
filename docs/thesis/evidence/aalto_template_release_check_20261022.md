# Aalto thesis template release check — 2026-10-22

## Finding

The official template page says its 2026-10-19 release updates the English, Finnish,
and Swedish TeX files to version 4.22, adds an AI-use disclosure example, and moves
the table of contents. The files currently served from that page do not match that
description: the downloaded English TeX file identifies itself as version 4.21,
dated 2026-02-19, and contains no AI-use disclosure section. The English PDF and the
full-package ZIP likewise match the February 2026 package contents. Treat this as an
upstream attachment mismatch; do not call the bytes on disk version 4.22.

## Reproducible attachment evidence

The public attachment metadata reports the following attachments created by Luis
Costa on 2026-10-19, each as attachment version 1:

| Attachment | Metadata size | Downloaded bytes / SHA-256 | Content observation |
|---|---:|---|---|
| `fullpackage20260219.zip` | 4,441,004 | 4,441,004 / `58d34ff94b70bc5f730b3f4c081eaf154b7e3da54c192db0adeb21b9040e956d` | Archive entries for the English `.tex` and `.pdf` are dated 2026-02-19. |
| `thesistemplate.tex` | 109,426 | 109,426 / `66d6fe86a6d43ac8285c7060f1999dad3c129e514128efd335653cd3046ccb28` | Header says `thesistemplate.tex version 4.21 (2026/02/19)`; no AI disclosure wording is present. |
| `thesistemplate_short.tex` | 37,901 | 37,901 / `ff59679103876e420b66e53a21f14889d8c97836cd5258e1295571299cfc4f33` | Header says version 4.21 (2026/02/19); no AI disclosure wording is present. |
| `thesistemplate.pdf` | 841,813 | 841,813 / `bfff48a3e5c39645fe4b7236d64520e2725bb06c709da2535a2c3648d226bcd4` | SHA-256 equals the PDF of the same name inside the downloaded ZIP. |

The `.tex` SHA-256 values were computed from the official direct downloads. The
English template file in the ZIP has the same SHA-256 as its direct download. The
ZIP and individual PDF/TeX attachments have `version=1` in the public attachment
metadata, so the mismatch is in the currently published attachment contents, not a
selection of an older attachment version.

## Submission implications

- Use the Aalto page announcement as evidence that a 4.22 update was intended, but
  do not use these 4.21 bytes as though they contain the announced changes.
- Resolve the official source mismatch before freezing the submission template. If
  that remains unresolved, use only the verified template bytes and have the
  supervisor confirm how to handle the announced but unavailable changes.
- Aalto's AI guidance requires a thesis statement describing AI use or non-use and
  prior supervisor approval of AI use. Preserve the existing AI-use log and obtain
  approval for the statement before finalizing it; do not invent a disclosure.
- Aalto's PDF/A instructions say its LaTeX template produces PDF/A-2b directly.
  Validate the final file and keep it below 100 MB as required by the submission
  instructions.

## Sources

- [Official Aalto LaTeX template page](https://wiki.aalto.fi/spaces/Aaltothesis/pages/69900685/Aalto+Thesis+LaTeX+Template), update comment dated 2026-10-19 and listed attachments.
- [Aalto guidance for use of AI in thesis work](https://www.aalto.fi/en/services/guidance-for-the-use-of-ai-in-thesis-work-at-the-bachelors-and-masters-level).
- [Aalto PDF/A creation instructions](https://www.aalto.fi/en/services/creating-a-pdfa-compliant-file-of-your-thesis).
- [Aalto thesis submission instructions](https://www.aalto.fi/en/news/submitting-theses-for-grading-as-pdfa-files).

## Live recheck — 2026-10-22 18:51 EEST

The official template page and attachment service were checked again. The page still
announces version 4.22 in its 2026-10-19 comment, but the current direct English TeX
download and short-template download have the same hashes and sizes recorded above.
The current full-package ZIP also has the same recorded hash and size. The public
attachment API identifies `thesistemplate.tex`, `thesistemplate_short.tex`, and
`fullpackage20260219.zip` as attachment version 1; their modification timestamps are
2026-10-19. The English TeX header still says version 4.21 (2026/02/19), and the ZIP
hash is unchanged. Thus the announced 4.22 source is still unavailable through the
official attachments checked here; this recheck does not resolve the mismatch.

Recheck method: download the three current official attachment URLs, compare their
SHA-256 values and byte counts with the table above, inspect the English TeX header,
and query the public attachment list at
`https://wiki.aalto.fi/rest/api/content/69900685/child/attachment?limit=200`.
