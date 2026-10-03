"""PCG32 random generator. Own implementation so a seed gives the same stream on every Python version
(the stdlib `random` module does not promise that for randint/choice/shuffle)."""
import math

_MASK64 = (1 << 64) - 1
_MULT = 6364136223846793005


class Rng:
    def __init__(self, seed=0, stream=0xDA3E39CB94B95BDB):
        self.state = 0
        self.inc = ((stream << 1) | 1) & _MASK64
        self.next_u32()
        self.state = (self.state + (seed & _MASK64)) & _MASK64
        self.next_u32()

    def next_u32(self):
        old = self.state
        self.state = (old * _MULT + self.inc) & _MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & 0xFFFFFFFF
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & 0xFFFFFFFF

    def random(self):
        """Uniform in [0, 1)."""
        return (self.next_u32() >> 8) / 16777216.0

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def below(self, n):
        if n <= 0:
            return 0
        threshold = ((1 << 32) - n) % n
        while True:
            r = self.next_u32()
            if r >= threshold:
                return r % n

    def randint(self, a, b):
        """Inclusive on both ends."""
        return a + self.below(b - a + 1)

    def chance(self, p):
        return self.random() < p

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def weighted(self, items):
        """items: list of (value, weight)."""
        total = sum(w for _, w in items)
        r = self.random() * total
        for v, w in items:
            if r < w:
                return v
            r -= w
        return items[-1][0]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]

    def fork(self, label):
        """Independent child stream: adding features does not disturb the others (stable output)."""
        h = 1469598103934665603
        for ch in str(label):
            h = ((h ^ ord(ch)) * 1099511628211) & _MASK64
        return Rng(self.state ^ h, stream=h | 1)
