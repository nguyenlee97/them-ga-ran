"""
Combo trade-up ("Nâng cấp lên Combo").

When the cart looks like the makings of a combo, suggest the combo that COVERS
everything the customer picked — framed by the price delta (savings, or "add a
drink + fries for only +Xk"). A distinct recommendation type from the strip.

We parse combo composition from the Vietnamese description once (e.g.
"3 Miếng Gà + 1 Khoai Tây Chiên (Vừa) + 3 ly Pepsi" → {chicken:3, side:1,
drink:3}) and match the cart's category counts against it.
"""
import re
from collections import Counter

_SIDE = r"khoai|popcorn|gà viên|phô mai viên|salad|bắp cải|súp|nghiền|cơm trắng"
_DRINK = r"pepsi|7up|lipton|nước|trà|\bly\b|\blon\b"
_DESSERT = r"bánh trứng|\bkem\b|sundae|ốc quế"
_CHICKEN = r"miếng gà|gà rán|gà lắc|gà quay|tender|phi-lê|xốt mắm|nanban"
_BURGER = r"burger"
_PASTA = r"mì ý"
_RICE = r"\bcơm\b"

_VND = lambda n: f"{n:,.0f}".replace(",", ".") + "đ"

# distinctive words to tell similar combos apart (ignore category/filler words)
_STOP = {"combo", "miếng", "phần", "burger", "gà", "ly", "lon", "xô", "cơm", "mì", "ý",
         "chiên", "khoai", "tây", "không", "đường", "vừa", "lớn", "đại", "tiêu", "chuẩn",
         "và", "kèm", "tặng", "1", "2", "3", "4", "5", "6", "9", "12"}


def _classify(part):
    s = part.lower()
    if re.search(_SIDE, s): return "side"
    if re.search(_DRINK, s): return "drink"
    if re.search(_DESSERT, s): return "dessert"
    if re.search(_BURGER, s): return "burger"
    if re.search(_PASTA, s): return "pasta"
    if re.search(_RICE, s): return "rice"
    if re.search(_CHICKEN, s): return "chicken"
    return None


def parse_components(desc):
    """Description → Counter of category → total qty (number found anywhere in the segment)."""
    comp = Counter()
    for part in re.split(r"[+,]", desc or ""):
        part = part.strip()
        if not part:
            continue
        m = re.search(r"(\d+)", part)          # first number ANYWHERE in the segment
        qty = int(m.group(1)) if m else 1
        cat = _classify(part)
        if cat:
            comp[cat] += qty
    return comp


def _distinctive(name):
    return {w for w in re.findall(r"[a-zà-ỹ]+", (name or "").lower()) if len(w) >= 4 and w not in _STOP}


def _product_cat(p):
    t = p.get("tags") or []
    for k in ("drink", "dessert", "side", "burger", "pasta", "rice", "chicken"):
        if k in t:
            return k
    return None


def best_combo_upsell(cart, prod_idx, max_excess=4):
    """cart: list of {sku, qty}. Returns a combo-upsell dict or None."""
    if not cart:
        return None
    by_id = {str(p.get("_id")): p for p in prod_idx.values()}

    cart_comp = Counter()
    alacarte = 0
    cart_skus = set()
    has_main = False
    cart_words = set()
    for line in cart:
        p = prod_idx.get(line.get("sku")) or by_id.get(str(line.get("productId")))
        if not p:
            continue
        if p.get("isCombo"):
            return None  # already ordering a combo
        cart_skus.add(p["sku"])
        qty = int(line.get("qty", 1))
        cat = _product_cat(p)
        if cat:
            cart_comp[cat] += qty
        if cat in ("chicken", "burger", "pasta", "rice"):
            has_main = True
            cart_words |= _distinctive(p.get("name_vi"))
        alacarte += (p.get("price") or 0) * qty

    if not has_main or not cart_comp:
        return None

    candidates = []
    for p in prod_idx.values():
        if not p.get("isCombo"):
            continue
        comp = parse_components(p.get("description", ""))
        if not comp:
            continue
        if all(comp.get(cat, 0) >= n for cat, n in cart_comp.items()):
            excess = sum(comp.values()) - sum(cart_comp.values())
            if 0 <= excess <= max_excess:
                desc_words = _distinctive(p.get("description", "") + " " + p.get("name_vi", ""))
                match_bonus = len(cart_words & desc_words)  # prefer the SAME item's combo
                candidates.append((excess, -match_bonus, p.get("price") or 0, p, comp))

    if not candidates:
        return None
    # tightest fit → best name match → cheapest
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    excess, _mb, price, combo, comp = candidates[0]

    delta = price - alacarte
    label = {"drink": "nước", "side": "khoai/món kèm", "chicken": "gà", "dessert": "tráng miệng"}
    extras = []
    for cat, n in comp.items():
        if n - cart_comp.get(cat, 0) > 0 and cat in label:
            extras.append(label[cat])
    extras_txt = ", ".join(dict.fromkeys(extras))

    if delta <= 0:
        copy = f"Lên {combo['name_vi']} — tiết kiệm {_VND(abs(delta))} so với mua lẻ!"
    elif extras_txt:
        copy = f"Thêm {extras_txt} — lên {combo['name_vi']} chỉ +{_VND(delta)}!"
    else:
        copy = f"Nâng cấp lên {combo['name_vi']} chỉ +{_VND(delta)}!"

    return {
        "type": "combo_upsell",
        "sku": combo["sku"],
        "productId": str(combo.get("_id", "")),
        "name": combo["name_vi"],
        "price": price,
        "oldPrice": combo.get("oldPrice"),
        "imageUrl": combo.get("imageUrl"),
        "alacartePrice": alacarte,
        "priceDelta": delta,
        "covers": list(cart_skus),
        "copy": copy,
    }
