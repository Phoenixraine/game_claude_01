"""Builds build_cockpit_v4.py = v3 header + shell_v4.py + v3 body/arms/export tail (kept as tail_v3.py after the first run)."""
import io, os
HERE = os.path.dirname(os.path.abspath(__file__))
rd = lambda n: io.open(os.path.join(HERE, n), encoding="utf-8").read()
head, shell, tail = rd("head_v4.py"), rd("shell_v4.py"), rd("tail_v4.py")
io.open(os.path.join(HERE, "build_cockpit_v4.py"), "w", encoding="utf-8", newline="\n").write(head + "\n" + shell + "\n" + tail)
print("assembled")
