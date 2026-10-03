"""python hy_grid.py <prefix> : overlays a grid in final-mech metres (82 m tall, feet at z=0, x centred) on the ortho renders."""
import sys, json
from PIL import Image, ImageDraw

pre = sys.argv[1]
J = json.load(open(pre + "_ortho.json"))
H = J["height"]; sc = J["scale"]; ctr = J["center"]; zmin = J["bbox_min"][2]
k = 82.0 / H
for view, axis in (("front", 0), ("side", 1)):
    im = Image.open(f"{pre}_ortho_{view}.png").convert("RGB"); d = ImageDraw.Draw(im)
    def px(v, c):
        return 500 + (v - c) / sc * 1000
    for zm in range(0, 90, 5):
        y = 500 - ((zm / k + zmin) - ctr[2]) / sc * 1000
        d.line([(0, y), (1000, y)], fill=(255, 0, 0) if zm % 10 == 0 else (255, 160, 160), width=1)
        d.text((2, y - 11), "z%d" % zm, fill=(200, 0, 0))
    for xm in range(-40, 41, 5):
        x = px(xm / k + ctr[axis], ctr[axis])
        d.line([(x, 0), (x, 1000)], fill=(0, 0, 255) if xm % 10 == 0 else (160, 160, 255), width=1)
        d.text((x + 2, 2), ("%d" % xm), fill=(0, 0, 200))
    im.save(f"{pre}_grid_{view}.png")
print("ok")
