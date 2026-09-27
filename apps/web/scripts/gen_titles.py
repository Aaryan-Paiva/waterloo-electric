from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1280, 200
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT_DIR = os.path.join(os.path.dirname(__file__), "out", "motion", "titled")
os.makedirs(OUT_DIR, exist_ok=True)

TITLES = {
    "01_demand_capacity": "Demand is outpacing local capacity",
    "02_vpp_devices": "Batteries. EV fleets. Flexible buildings.",
    "03_lifecycle": "Request. Offer. Dispatch.",
    "04_title_reveal": "CapacityOS",
    "05_question_overlay": "Can this zone handle it?",
    "06_pilot_pathway": "From pilot to zone-wide rollout",
}

INK = (29, 35, 32, 255)
CREAM = (251, 247, 238, 235)

for name, text in TITLES.items():
    size = 60 if name != "04_title_reveal" else 72
    font = ImageFont.truetype(FONT, size)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 36, 20
    box = [(W - tw) / 2 - pad_x, (H - th) / 2 - pad_y - bbox[1], (W + tw) / 2 + pad_x, (H + th) / 2 + pad_y - bbox[1]]
    draw.rounded_rectangle(box, radius=16, fill=CREAM)
    draw.text(((W - tw) / 2 - bbox[0], (H - th) / 2 - bbox[1]), text, font=font, fill=INK)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))
    print("wrote", name)
