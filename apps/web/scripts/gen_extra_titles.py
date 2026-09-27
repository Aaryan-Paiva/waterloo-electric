from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1920, 1080
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
OUT_DIR = os.path.join(os.path.dirname(__file__), "out", "motion", "extra")
os.makedirs(OUT_DIR, exist_ok=True)

CREAM = (251, 247, 238, 255)
INK = (29, 35, 32, 255)
ACCENTS = {"utility": (58, 130, 199), "aggregator": (216, 148, 44), "planner": (43, 140, 116)}

def persona_card(name, label, question):
    img = Image.new("RGBA", (W, H), CREAM)
    draw = ImageDraw.Draw(img)
    accent = ACCENTS[name]
    # accent bar on left
    draw.rectangle([0, 0, 24, H], fill=accent)
    # label
    font_label = ImageFont.truetype(FONT_BOLD, 44)
    draw.text((160, 380), label, font=font_label, fill=accent)
    # question
    font_q = ImageFont.truetype(FONT_BOLD, 74)
    # wrap question manually if too long
    words = question.split()
    lines, cur = [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if draw.textlength(test, font=font_q) > W - 320:
            lines.append(cur)
            cur = w_
        else:
            cur = test
    if cur:
        lines.append(cur)
    y = 460
    for line in lines:
        draw.text((160, y), line, font=font_q, fill=INK)
        y += 90
    img.save(os.path.join(OUT_DIR, f"{name}.png"))
    print("wrote", name)

ACCENTS["07-utility"] = ACCENTS.pop("utility")
ACCENTS["08-aggregator"] = ACCENTS.pop("aggregator")
ACCENTS["09-planner"] = ACCENTS.pop("planner")
persona_card("07-utility", "UTILITY PLANNER", "How much of this capacity shortfall could flexibility address?")
persona_card("08-aggregator", "AGGREGATOR", "What participation, incentives, and resource mix should we target?")
persona_card("09-planner", "MUNICIPAL PLANNER / CONSULTANT", "Which designs actually hold up across different conditions?")

# end card
img = Image.new("RGBA", (W, H), CREAM)
draw = ImageDraw.Draw(img)
font_title = ImageFont.truetype(FONT_BOLD, 130)
font_tag = ImageFont.truetype(FONT_REG, 48)
font_tag2 = ImageFont.truetype(FONT_REG, 40)

# small amber square accent above title
sq = 90
draw.rounded_rectangle([(W - sq) / 2, 260, (W + sq) / 2, 260 + sq], radius=18, fill=(242, 167, 46, 255))

title = "CapacityOS"
tw = draw.textlength(title, font=font_title)
draw.text(((W - tw) / 2, 400), title, font=font_title, fill=INK)

tag1 = "Make room for what's next."
tw1 = draw.textlength(tag1, font=font_tag)
draw.text(((W - tw1) / 2, 580), tag1, font=font_tag, fill=INK)

tag2 = "Design the VPP before you deploy it."
tw2 = draw.textlength(tag2, font=font_tag2)
draw.text(((W - tw2) / 2, 650), tag2, font=font_tag2, fill=(90, 95, 90, 255))

img.save(os.path.join(OUT_DIR, "10-endcard.png"))
print("wrote 10-endcard")
