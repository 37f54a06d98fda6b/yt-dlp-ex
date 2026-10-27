import base64
import urllib.parse

from .common import InfoExtractor
from ..utils import unescapeHTML

import re
import unicodedata

from .common import InfoExtractor
from ..utils import parse_duration, parse_iso8601, unescapeHTML
import datetime
import re
import unicodedata

# def _clean_title(raw, fallback):
#     t = unicodedata.normalize("NFKC", raw)
#     t = re.sub(r"\s+on\s+(?:the\s+)?Sexy\s*Porn(?:\s+OG)?\s*$", "", t, flags=re.I)  # site suffix
#     t = re.sub(r"https?://\S+|\b[\w-]+\.(?:com|net|org|to|so|co|club)\b\S*", " ", t)  # URLs / domains
#     t = re.sub(r"#\S+", " ", t)  # hashtags
#     # dates: 27.10.2026, 17-10-2026, 2026-10-17, 17/10/26, and a bare (2026)
#     t = re.sub(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b|\b\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\b", " ", t)
#     t = re.sub(r"\(\s*(?:19|20)\d{2}\s*\)", " ", t)
#     t = re.sub(r"^\W*(?:new|watch/download|nsfw)\b\W*", "", t, flags=re.I)  # leading "New", etc.
#     t = re.sub(r"[^\w\s\-\'&,.()]", " ", t)  # drop emoji and odd symbols, keep unicode letters
#     t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)  # empty brackets left behind
#     t = re.sub(r"\s+", " ", t).strip(" -_.,&")
#     if len(t) > 100:
#         t = t[:100].rsplit(" ", 1)[0]
#     return t or fallback


_URL_RE = re.compile(
    r"https?://\S+|(?<![\w@])(?:[\w-]+\.)+(?:com|net|org|to|so|co|club|li|tv|cc|io)\b\S*", re.I
)
_DATE_RE = re.compile(
    r"(?<!\d)(?:(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})|(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4}|\d{2}))(?!\d)"
)


def _norm_date(m, upload_date):
    try:
        if m.group(1):
            y, mo, d = int(m[1]), int(m[2]), int(m[3])
        else:
            a, b, y = int(m[4]), int(m[5]), int(m[6])
            y += 2000 if y < 100 else 0
            d, mo = (b, a) if b > 12 else (a, b)  # day-first unless clearly month-first
        iso = datetime.date(y, mo, d).isoformat()
    except ValueError:
        return m.group(0)
    return " " if iso.replace("-", "") == upload_date else iso


def _build_title(raw, upload_date, fallback, base_max=100, total_max=150):
    t = unicodedata.normalize("NFKC", raw)
    t = t.translate({0x2018: "'", 0x2019: "'", 0x02BC: "'", 0x201C: '"', 0x201D: '"'})
    t = re.sub(r'(?<=\w)"(?=\w)', "'", t)

    # hashtags: collect (de-duplicated, order kept), then remove from the text
    tags, seen = [], set()
    for tag in re.findall(r"#+([^\s#]+)", t):
        tag = re.sub(r"[^\w\-]", "", tag)
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    t = re.sub(r"#+[^\s#]*", " ", t)

    t = re.sub(r"\s+on\s+(?:the\s+)?Sexy\s*Porn(?:\s+OG)?\s*$", "", t, flags=re.I)  # site suffix
    t = _URL_RE.sub(" ", t)  # links to other hosts
    t = re.sub(r"\[\s*\d{1,2}:\d{2}(?::\d{2})?\s*\]", " ", t)  # [28:50] duration
    t = _DATE_RE.sub(lambda m: _norm_date(m, upload_date), t)
    t = re.sub(r"^\W*(?:new|watch/download)\b\W*", "", t, flags=re.I)  # boilerplate label
    t = re.sub(r"[^\w\s\-'&,.()+!]", " ", t)  # emoji / odd symbols
    t = re.sub(r"\(\s*\)", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -_.,&")

    base = t if len(t) <= base_max else t[:base_max].rsplit(" ", 1)[0]
    base = base or ("" if tags else fallback)

    def assemble(n):
        return " ".join(filter(None, [base, f'[{" ".join(tags[:n])}]' if n else ""]))

    n = len(tags)
    while n and len(assemble(n)) > total_max:
        n -= 1
    return assemble(n) or fallback, tags


class MySxyprnIE(InfoExtractor):
    _VALID_URL = r"https?://(?:www\.)?sxyprn\.com/post/(?P<id>[\da-f]+)\.html"

    @staticmethod
    def _digit_sum(s):
        return sum(int(c) for c in s if c.isdigit())

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        # vnfo = self._search_regex(r'data-vnfo="([^"]+)"', webpage, "vnfo")
        # path = self._parse_json(unescapeHTML(vnfo), video_id)[video_id]
        vnfo = self._search_regex(
            r"""data-vnfo\s*=\s*(?P<q>["'])(?P<json>.+?)(?P=q)""", webpage, "vnfo", group="json"
        )
        path = self._parse_json(unescapeHTML(vnfo), video_id)[video_id]

        # import re
        # title = self._og_search_title(webpage, default=video_id)
        # title = re.sub(r"\s+on SexyPorn OG$", "", title)
        # title = re.sub(r"\s*#\S+", "", title)  # drop hashtags
        # title = re.sub(r"\s+", " ", title).strip() or video_id

        # ['', 'cdn', 'c8', A, B, timestamp, token1, 'token2.vid']
        parts = path.split("/")
        s1 = self._digit_sum(parts[6])
        s2 = self._digit_sum(parts[7].rpartition(".")[0])
        host = urllib.parse.urlparse(url).hostname.removeprefix("www.")

        parts[1] += "8"
        parts[5] = str(int(parts[5]) - s1 - s2)
        parts.insert(2, base64.b64encode(f"{s1}-{host}-{s2}".encode()).decode().replace("=", "."))
        raw_title = self._og_search_title(webpage, default=video_id)  # use og:title, not <title>
        timestamp = parse_iso8601(self._html_search_meta("uploadDate", webpage))
        upload_date = (
            datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y%m%d")
            if timestamp
            else None
        )
        title, tags = _build_title(raw_title, upload_date, video_id)

        return {
            "id": video_id,
            "title": title,
            "tags": tags,
            "timestamp": timestamp,
            "duration": parse_duration(self._html_search_meta("duration", webpage)),
            "url": f"https://{host}" + "/".join(parts),
            "ext": "mp4",
            "uploader": self._search_regex(
                r'class="a_name"[^>]*>([^<]+)<', webpage, "uploader", default=None
            ),
            "http_headers": {"Referer": url},
        }

        # return {
        #     "title": _clean_title(raw_title, video_id),
        #     "tags": re.findall(r"#(\w+)", raw_title),
        #     "timestamp": parse_iso8601(self._html_search_meta("uploadDate", webpage)),
        #     "title": self._og_search_title(webpage, default=video_id),
