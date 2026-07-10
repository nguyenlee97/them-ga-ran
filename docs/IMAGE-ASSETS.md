# Kiosk image assets — sizes to generate

The kiosk has **styled fallbacks**, so it looks right even before you add images.
Drop the real graphics into `kiosk/public/assets/` with these exact filenames and
sizes and they'll appear automatically.

| File | Size (px) | Where it shows | Notes |
|---|---|---|---|
| `kiosk/public/assets/welcome-hero.png` | **1080 × 1400** (portrait) | Welcome screen, the big promo block | The KFC Rewards "ĐĂNG KÝ THÀNH VIÊN / MỞ KHÓA ƯU ĐÃI" graphic with the 3/5/7% tiers, the 25K deal, and QR codes. Occupies the middle of the screen between the red header and the dine-mode buttons. |
| `kiosk/public/assets/menu-banner.png` | **1080 × 264** (wide) | Top of the menu page | The horizontal KFC Rewards registration banner (logo + phone mockup + 3/5/7% + QR). |

## Not needed
- **Product photos** — pulled live from KFC's CDN (`static.kfcvietnam.com.vn/images/items/lg/<CODE>.jpg`), already wired into every menu/cart/reco card.
- **Login popup** — uses a built-in scanner illustration + text (no marketing image required). If you want the little "how to scan" inset photo from the real kiosk, add `kiosk/public/assets/scan-hint.png` at **360 × 360** and tell me — I'll slot it in.

## Format
PNG preferred (JPG fine — just name it `.png` or tell me to switch the extension). Export at the sizes above (they're 2× the on-screen size for crispness on the portrait kiosk).

## Design container
The kiosk renders in a portrait column **480 px wide** (scales up on a real kiosk screen). Keep hero art vertically composed; keep the banner short and wide.
