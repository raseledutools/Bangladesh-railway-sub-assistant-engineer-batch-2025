"""
যোগদানপত্র জেনারেটর — FastAPI backend
এক ক্লিকে A4 ভেক্টর PDF ডাউনলোড, কোনো print dialog ছাড়াই।

Playwright দিয়ে server-side চিঠির HTML রেন্ডার করে সরাসরি PDF বানানো হয়।
কোনো ডেটা সেভ হয় না — প্রতিটা request স্টেটলেস (in-memory generate করে ফেরত)।
"""

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="যোগদানপত্র জেনারেটর")

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)

# একটাই Playwright/Chromium instance পুরো অ্যাপের লাইফটাইমে ব্যবহার হবে,
# প্রতি রিকোয়েস্টে নতুন ব্রাউজার চালু করা খুব ধীর হবে।
_playwright_ctx = None
_browser = None


@app.on_event("startup")
async def startup_event():
    global _playwright_ctx, _browser
    _playwright_ctx = await async_playwright().start()
    _browser = await _playwright_ctx.chromium.launch(
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )


@app.on_event("shutdown")
async def shutdown_event():
    global _playwright_ctx, _browser
    if _browser:
        await _browser.close()
    if _playwright_ctx:
        await _playwright_ctx.stop()


class LetterPayload(BaseModel):
    font: str = "font-noto"
    recipient: str = ""
    ministry: str = ""
    addr1: str = ""
    addr2: str = ""
    org: str = ""
    post: str = ""
    shakha: str = ""
    pragyaponDate: str = ""
    pragyaponNo: str = ""
    betonScale: str = ""
    grade: str = ""
    betonOrder: str = ""
    joinDate: str = ""
    joinDay: str = ""
    letterDate: str = ""
    name: str = ""
    regNo: str = ""
    merit: str = ""
    district: str = ""
    mobile: str = ""
    enclosures: str = ""


ALLOWED_FONTS = {
    "font-noto",
    "font-kalpurush",
    "font-solaiman",
    "font-siyam",
    "font-sutonny",
}

PLACEHOLDER_WARN = '<span class="placeholder-warn">[{}]</span>'


async def _fit_single_page(page) -> None:
    """
    চিঠির কন্টেন্ট যদি এক A4 পেজের চেয়ে লম্বা হয়ে যায়, ফন্ট-সাইজ বাইনারি-সার্চ
    করে এমন একটা scale বের করা হয় যাতে পুরো চিঠি একটাই পেজে ফিট হয়
    (Word এর মতো অফিসিয়াল চিঠি সাধারণত এক পেজেই থাকে)।
    """
    measurements = await page.evaluate(
        """
        () => {
            const node = document.getElementById('letterPage');
            const styles = window.getComputedStyle(node);
            return {
                baseFontSize: parseFloat(styles.fontSize),
                widthPx: node.getBoundingClientRect().width
            };
        }
        """
    )

    page_width_mm = 210
    page_height_mm = 297
    mm_to_px = measurements["widthPx"] / page_width_mm
    target_px = page_height_mm * mm_to_px
    base_font_size = measurements["baseFontSize"]

    async def set_scale(scale: float) -> float:
        return await page.evaluate(
            """
            (args) => {
                const node = document.getElementById('letterPage');
                node.style.fontSize = (args.baseFontSize * args.scale) + 'px';
                return node.scrollHeight;
            }
            """,
            {"baseFontSize": base_font_size, "scale": scale},
        )

    scroll_height = await set_scale(1.0)
    if scroll_height <= target_px:
        return  # আগেই এক পেজে ফিট হচ্ছে, কিছু করার দরকার নেই

    lo, hi = 0.5, 1.0  # কখনো ৫০% এর নিচে শ্রিংক করব না, পড়া যাবে না তাহলে
    for _ in range(10):  # ১০ বার বাইনারি সার্চই যথেষ্ট precision এর জন্য
        mid = (lo + hi) / 2
        h = await set_scale(mid)
        if h > target_px:
            hi = mid  # এখনো বড়, আরও শ্রিংক করতে হবে
        else:
            lo = mid  # ফিট হচ্ছে, আরেকটু বড় করার চেষ্টা করি

    await set_scale(lo)  # সবচেয়ে বড় যে সাইজে ফিট হয়, সেটাতেই সেট করা


def ph(value: str, fallback_label: str) -> str:
    """খালি থাকলে লাল warning placeholder, নাহলে raw value (template auto-escape করবে)।"""
    value = (value or "").strip()
    if not value:
        return PLACEHOLDER_WARN.format(fallback_label)
    return value


def build_letter_context(data: LetterPayload) -> dict:
    font_class = data.font if data.font in ALLOWED_FONTS else "font-noto"

    enclosures_raw = (data.enclosures or "").strip()
    enclosures = []
    if enclosures_raw:
        for line in enclosures_raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"[।.]+\s*$", "", line)
            enclosures.append(line)

    # Note: ph() ফলব্যাক warning HTML হিসেবেই বসবে, তাই raw markup ব্যবহার
    # করছি (Jinja2 autoescape থাকায় টেমপ্লেটে `| safe` লাগাতে হবে)।
    return {
        "font_class": font_class,
        "letter_date": ph(data.letterDate, "তারিখ"),
        "recipient": ph(data.recipient, "প্রাপকের পদবি"),
        "ministry": ph(data.ministry, "মন্ত্রণালয়/দপ্তর"),
        "addr1": data.addr1.strip(),
        "addr2": data.addr2.strip(),
        "org": ph(data.org, "প্রতিষ্ঠানের নাম"),
        "post": ph(data.post, "পদের নাম"),
        "shakha": ph(data.shakha, "শাখা"),
        "pragyapon_date": ph(data.pragyaponDate, "তারিখ"),
        "pragyapon_no": ph(data.pragyaponNo, "প্রজ্ঞাপন নম্বর"),
        "beton_scale": ph(data.betonScale, "বেতন স্কেল"),
        "grade": ph(data.grade, "গ্রেড"),
        "beton_order": ph(data.betonOrder, "বেতন আদেশ"),
        "join_date": ph(data.joinDate, "যোগদানের তারিখ"),
        "join_day": ph(data.joinDay, "বার"),
        "name": ph(data.name, "প্রার্থীর নাম"),
        "reg_no": ph(data.regNo, "রেজি নং"),
        "merit": ph(data.merit, "মেধাক্রম"),
        "district": ph(data.district, "জেলা"),
        "mobile": ph(data.mobile, "মোবাইল"),
        "enclosures": enclosures,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.post("/generate-pdf")
async def generate_pdf(payload: LetterPayload):
    if _browser is None:
        raise HTTPException(status_code=503, detail="সার্ভার এখনো প্রস্তুত হচ্ছে, আবার চেষ্টা করুন।")

    context = build_letter_context(payload)
    template = jinja_env.get_template("letter.html")

    # ph() থেকে আসা warning span গুলো template এ escape হয়ে যাবে যদি autoescape
    # থাকে, তাই এখানে Markup দিয়ে নিরাপদে mark করছি — কিন্তু user input ও সেই
    # একই ফিল্ডে আসে, তাই আগে escape করে fallback span বসাচ্ছি ম্যানুয়ালি।
    from markupsafe import Markup, escape

    def safe_or_escaped(value: str) -> Markup:
        if value.startswith('<span class="placeholder-warn">'):
            return Markup(value)
        return Markup(escape(value))

    for key in [
        "letter_date", "recipient", "ministry", "org", "post", "shakha",
        "pragyapon_date", "pragyapon_no", "beton_scale", "grade",
        "beton_order", "join_date", "join_day", "name", "reg_no",
        "merit", "district", "mobile",
    ]:
        context[key] = safe_or_escaped(context[key])

    context["addr1"] = Markup(escape(context["addr1"]))
    context["addr2"] = Markup(escape(context["addr2"]))
    context["enclosures"] = [Markup(escape(e)) for e in context["enclosures"]]

    html_content = template.render(**context)

    page = await _browser.new_page()
    try:
        await page.set_content(html_content, wait_until="networkidle")
        # ফন্ট গুলো ঠিকমতো লোড হওয়ার জন্য
        await page.evaluate("document.fonts.ready")

        # A4 পেজের উচ্চতা px এ (page.html এ .page width 210mm রাখা আছে,
        # তাই rendered px width দিয়ে mm-to-px অনুপাত বের করে target height হিসাব করি)
        await _fit_single_page(page)

        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
    finally:
        await page.close()

    name_for_file = re.sub(r"[^\u0980-\u09FFa-zA-Z0-9]+", "_", payload.name.strip() or "যোগদানপত্র")
    filename = f"যোগদানপত্র_{name_for_file}.pdf"
    # বাংলা ফাইলনেম সব ব্রাউজারে ঠিকভাবে কাজ করার জন্য RFC 5987 ফরম্যাট
    # (filename* ) ব্যবহার করছি, পাশাপাশি পুরনো ক্লায়েন্টের জন্য ASCII fallback।
    from urllib.parse import quote

    ascii_fallback = "joindata_letter.pdf"
    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{encoded_filename}"
            )
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
