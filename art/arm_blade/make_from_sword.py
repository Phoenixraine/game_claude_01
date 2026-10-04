"""Derives build_arm_blade.py from ../sword/build_sword.py: same blade (x 5.4..61), but the hilt / crossguard / handle are replaced by a bracer
housing the blade slides out of (the blade emerges from the arm instead of being held)."""
import io, os

here = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(here, "..", "sword", "build_sword.py"), encoding="utf-8").read()
a = src.index("# ricasso block + guard")
b = src.index("ob = S.finish()")
housing = '''# bracer housing: the blade is a part of the arm. A long armoured sleeve (x -16..5.4) swallows the fist and the wrist,
# the blade slides out of its mouth; hydraulic rams run along both sides, vents and orange accents break up the mass.
S.box((5.0, 0.0, 0.0), (1.6, 6.6, 4.4), cls=1, bevel=0.12)                       # mouth plate
S.box((5.9, 0.0, 0.0), (1.2, 5.2, 2.0), cls=0, bevel=0.08)                       # blade root block
S.box((-5.5, 0.0, 0.0), (21.0, 7.4, 5.4), cls=0, bevel=0.35)                     # main sleeve
S.box((-5.5, 0.0, 3.0), (19.0, 6.2, 1.0), cls=1, bevel=0.15)                     # upper armour plate
S.box((-5.5, 0.0, -3.0), (19.0, 6.2, 1.0), cls=1, bevel=0.15)                    # lower armour plate
S.box((-14.0, 0.0, 0.0), (3.0, 8.4, 6.4), cls=0, bevel=0.3)                      # elbow-side cuff
for sgn in (1, -1):
    S.cyl((-12.0, sgn * 4.6, 1.2), (3.5, sgn * 4.6, 1.2), 0.75, cls=1, seg=14)   # ram barrels
    S.cyl((3.0, sgn * 4.6, 1.2), (5.2, sgn * 4.6, 1.2), 0.45, cls=0, seg=12)    # ram rods
    for k in range(5):
        S.box((-9.5 + k * 2.4, sgn * 3.75, 0.0), (1.1, 0.35, 3.4), cls=4 if k % 2 == 0 else 3, bevel=0.04)   # vents
    S.box((-1.5, sgn * 3.2, 3.55), (5.0, 0.5, 0.35), cls=2, bevel=0.03)          # glowing seam
    S.box((4.7, sgn * 3.2, 0.0), (0.5, 0.35, 3.8), cls=4, bevel=0.03)
for k in range(6):
    S.box((-10.0 + k * 2.5, 0.0, 3.62), (0.7, 3.4, 0.28), cls=0, bevel=0.03)     # ribs on top
S.box((-15.6, 0.0, 0.0), (0.6, 4.0, 3.0), cls=2, bevel=0.04)                     # rear power glow
'''
out = src[:a] + housing + src[b:]
out = out.replace("SM_Sword", "SM_ArmBlade").replace("preview_sword", "preview_armblade")
out = out.replace("The duel sword of the mechs", "The mechs' arm blade (derived from the sword)", 1)
io.open(os.path.join(here, "build_arm_blade.py"), "w", encoding="utf-8", newline="\n").write(out)
print("written")
