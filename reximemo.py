from __future__ import annotations

import html
import io
import math
from pathlib import Path
from urllib.parse import urlencode

from PIL import Image

from DB import Database
from Hatenatools import PPM, UGO
from hatena import client_ip, request_args, request_headers, request_path
from reximemo_image_formats import encode_image

ROOT_HOST = "flipnote.hatena.com"
ROOT = Path(__file__).resolve().parent


def region_from_request(request):
    for part in request_path(request).split("/"):
        if part.startswith("v2-"):
            return part[3:]
    return "xx"


def host_for_region(region):
    return "ugomemo.hatena.ne.jp" if region == "jp" else ROOT_HOST


def dsi_url(request, suffix):
    region = region_from_request(request)
    return f"http://{host_for_region(region)}/ds/v2-{region}/{str(suffix).lstrip('/')}"


def current_account(request):
    return Database.account_for_ip(client_ip(request))


def current_creator(request, *, fsid="", display_name=""):
    account = current_account(request)
    return Database.get_or_create_creator(
        client_ip(request),
        int(account["id"]) if account else None,
        fsid=fsid,
        display_name=display_name,
    )


def keyboard_value(request):
    return request_headers(request).get("x-email-addr", "").strip()


def dialog(request, message, status=200):
    request.setResponseCode(int(status))
    request.setHeader(b"X-DSi-Dialog-Type", b"1")
    request.setHeader(b"content-type", b"text/plain")
    return str(message).encode("utf-16le")


def forward(request, target):
    request.setHeader(b"X-DSi-Forwarder", str(target).encode("ascii", "ignore"))


def html_page(request, title, body, extra_head=""):
    request.setHeader(b"content-type", b"text/html; charset=utf-8")
    page = f"""<!doctype html><html><head><title>{html.escape(str(title))}</title>
<meta name="uppertitle" content="{html.escape(str(title), quote=True)}">
<link rel="stylesheet" type="text/css" href="http://{ROOT_HOST}/css/ds/common.css">
<link rel="stylesheet" type="text/css" href="http://{ROOT_HOST}/css/ds/basic.css">
<link rel="stylesheet" type="text/css" href="http://{ROOT_HOST}/css/ds/ose.css">
{extra_head}</head><body><div class="container">{body}</div></body></html>"""
    return page.encode("utf-8")


def query_int(request, name, default=1, minimum=1, maximum=1000000):
    try:
        n = int(request_args(request).get(name, [str(default)])[0])
    except (TypeError, ValueError):
        n = default
    return min(maximum, max(minimum, n))


def make_menu(layout=(4,), title=None, subtitle_top="", subtitle_bottom="", left="", right="", buttons=None, dropdowns=None, corner=None):
    ugo = UGO()
    ugo.Loaded = True
    ugo.Items = [("layout", tuple(layout))]
    if title is not None:
        ugo.Items.append(("topscreen text", [str(title), str(left), str(right), str(subtitle_top), str(subtitle_bottom)], 0))
    for d in dropdowns or []:
        ugo.Items.append(("category", d["url"], d["label"], bool(d.get("selected"))))
    if corner:
        ugo.Items.append(("post", corner["url"], corner["label"]))
    embed_index = 0
    for b in buttons or []:
        if b.get("thumbnail") is not None:
            ugo.Items.append((
                "button", 3, b.get("label", ""), b["url"],
                (str(b.get("stars", 0)), str(b.get("lock", 765)), "573", "0"),
                (b.get("embed_name", "thumb.tmb"), b["thumbnail"]),
            ))
            embed_index += 1
        elif b.get("icon_ntft") is not None:
            icon_data = bytes(b["icon_ntft"])
            if len(icon_data) != 2048:
                raise ValueError("UGO menu icons must be 32x32 NTFT data")
            ugo.Items.append((
                "button", int(b.get("icon_trait", embed_index)), b.get("label", ""), b["url"],
                ("", "0"), (b.get("embed_name", "icon.ntft"), icon_data),
            ))
            embed_index += 1
        else:
            ugo.Items.append(("button", int(b.get("icon", 100)), b.get("label", ""), b["url"], ("", "0"), None))
    return ugo.Pack()


def placeholder_icon(name="browse"):
    path = ROOT / "hatenadir" / "images" / "ds" / f"{name}.ntft"
    return path.read_bytes()


def flipnote_buttons(request, rows):
    buttons = []
    for fn in rows:
        try:
            tmb = Database.GetFlipnoteTMB(fn["creator_fsid"], fn["filename"])
        except OSError:
            continue
        buttons.append({
            "label": "",
            "url": dsi_url(request, f"movie/{fn['creator_fsid']}/{fn['filename']}.htm"),
            "thumbnail": tmb,
            "embed_name": fn["filename"] + ".tmb",
            "stars": int(fn.get("stars") or 0),
            "lock": 765,
        })
    return buttons


def pagination_buttons(request, base, page, total, per_page=50, params=None):
    params = dict(params or {})
    max_page = max(1, int(math.ceil(total / float(per_page))))
    out = []
    if page > 1:
        q = dict(params); q["page"] = page - 1
        out.append({"label": "Previous Page", "url": dsi_url(request, base) + "?" + urlencode(q), "icon": 116})
    if page < max_page:
        q = dict(params); q["page"] = page + 1
        out.append({"label": "Next Page", "url": dsi_url(request, base) + "?" + urlencode(q), "icon": 115})
    return out


def ppm_first_frame_image(raw):
    ppm = PPM().Read(raw, ReadFrames=True, ReadSound=False)
    if not ppm:
        raise ValueError("Invalid PPM")
    frame = ppm.GetFrame(0)
    if frame is False or frame is None:
        raise ValueError("Missing first frame")
    data = frame.tobytes(order="F")
    return Image.frombytes("RGBA", (len(frame), len(frame[0])), data)


def ppm_thumbnail_png(raw, size=(256, 192)):
    image = ppm_first_frame_image(raw).convert("RGB")
    image.thumbnail(size, Image.Resampling.NEAREST)
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def comment_npf(comment_id, width=128, height=64):
    raw = Database.comment_ppm(int(comment_id))
    if raw is None:
        return None
    image = ppm_first_frame_image(raw).convert("RGBA")
    image = image.resize((int(width), int(height)), Image.Resampling.NEAREST)
    return encode_image(image, "npf").data
