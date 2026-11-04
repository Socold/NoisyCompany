"""Minimal QR Code encoder (byte mode, ISO/IEC 18004), stdlib only.

Used to print collective share codes (feature `collective_noise`) as a QR code on the
terminal or as SVG, so a household can scan it instead of copying 400 characters. It
follows the reference algorithm of Project Nayuki's QR Code generator (MIT licence):
Reed-Solomon over GF(256), block interleaving, the 8 masks with the standard penalty.
"""

from __future__ import annotations

ECC_L, ECC_M = 0, 1
_FORMAT_BITS = {ECC_L: 1, ECC_M: 0}
_ECC_PER_BLOCK = {
    ECC_L: (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28,
            28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    ECC_M: (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26,
            26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
}
_NUM_BLOCKS = {
    ECC_L: (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12,
            12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    ECC_M: (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20,
            21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
}


def _raw_modules(ver: int) -> int:
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        result -= (25 * n - 10) * n - 55
        if ver >= 7:
            result -= 36
    return result


def _data_codewords(ver: int, ecl: int) -> int:
    return _raw_modules(ver) // 8 - _ECC_PER_BLOCK[ecl][ver] * _NUM_BLOCKS[ecl][ver]


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


class QrCode:
    def __init__(self, ver: int, ecl: int, data: list[int], mask: int = -1) -> None:
        self.version, self.ecl = ver, ecl
        self.size = ver * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self._func = [[False] * self.size for _ in range(self.size)]
        self._draw_function_patterns()
        self._draw_codewords(self._add_ecc_and_interleave(data))
        if mask == -1:
            best = None
            for m in range(8):
                self._apply_mask(m)
                self._draw_format_bits(m)
                p = self._penalty()
                if best is None or p < best[0]:
                    best = (p, m)
                self._apply_mask(m)  # XOR again: undo
            mask = best[1]  # type: ignore[index]
        self.mask = mask
        self._apply_mask(mask)
        self._draw_format_bits(mask)

    # ------------------------------------------------------------ function patterns
    def _set_func(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self._func[y][x] = True

    def _draw_function_patterns(self) -> None:
        for i in range(self.size):
            self._set_func(6, i, i % 2 == 0)
            self._set_func(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (self.size - 4, 3), (3, self.size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < self.size and 0 <= y < self.size:
                        dist = max(abs(dx), abs(dy))
                        self._set_func(x, y, dist not in (2, 4))
        pos = self._alignment_positions()
        n = len(pos)
        for i in range(n):
            for j in range(n):
                if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set_func(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format_bits(0)
        self._draw_version()

    def _alignment_positions(self) -> list[int]:
        if self.version == 1:
            return []
        num = self.version // 7 + 2
        step = (self.version * 8 + num * 3 + 5) // (num * 4 - 4) * 2
        result = [self.size - 7 - i * step for i in range(num - 1)] + [6]
        return list(reversed(result))

    def _draw_format_bits(self, mask: int) -> None:
        data = _FORMAT_BITS[self.ecl] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: (bits >> i) & 1 != 0  # noqa: E731
        for i in range(6):
            self._set_func(8, i, bit(i))
        self._set_func(8, 7, bit(6))
        self._set_func(8, 8, bit(7))
        self._set_func(7, 8, bit(8))
        for i in range(9, 15):
            self._set_func(14 - i, 8, bit(i))
        for i in range(8):
            self._set_func(self.size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._set_func(8, self.size - 15 + i, bit(i))
        self._set_func(8, self.size - 8, True)

    def _draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.version << 12 | rem
        for i in range(18):
            dark = (bits >> i) & 1 != 0
            a, b = self.size - 11 + i % 3, i // 3
            self._set_func(a, b, dark)
            self._set_func(b, a, dark)

    # ------------------------------------------------------------ data
    def _add_ecc_and_interleave(self, data: list[int]) -> list[int]:
        ver, ecl = self.version, self.ecl
        num_blocks = _NUM_BLOCKS[ecl][ver]
        ecc_len = _ECC_PER_BLOCK[ecl][ver]
        raw = _raw_modules(ver) // 8
        num_short = num_blocks - raw % num_blocks
        short_len = raw // num_blocks
        divisor = _rs_divisor(ecc_len)
        blocks = []
        k = 0
        for i in range(num_blocks):
            n = short_len - ecc_len + (0 if i < num_short else 1)
            dat = data[k:k + n]
            k += n
            ecc = _rs_remainder(dat, divisor)
            if i < num_short:
                dat = dat + [0]
            blocks.append(dat + ecc)
        result = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                if i != short_len - ecc_len or j >= num_short:
                    result.append(blk[i])
        return result

    def _draw_codewords(self, data: list[int]) -> None:
        i = 0
        right = self.size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(self.size):
                for j in range(2):
                    x = right - j
                    upward = (right + 1) & 2 == 0
                    y = self.size - 1 - vert if upward else vert
                    if not self._func[y][x] and i < len(data) * 8:
                        self.modules[y][x] = (data[i >> 3] >> (7 - (i & 7))) & 1 != 0
                        i += 1
            right -= 2

    def _apply_mask(self, mask: int) -> None:
        fn = (lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0,
              lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0,
              lambda x, y: (x // 3 + y // 2) % 2 == 0,
              lambda x, y: x * y % 2 + x * y % 3 == 0,
              lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
              lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0)[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self._func[y][x] and fn(x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def _penalty(self) -> int:
        size, m = self.size, self.modules
        result = 0
        lines = [m[y] for y in range(size)] + [[m[y][x] for y in range(size)] for x in range(size)]
        for line in lines:
            run, color = 0, None
            for v in line:
                if v == color:
                    run += 1
                    if run == 5:
                        result += 3
                    elif run > 5:
                        result += 1
                else:
                    color, run = v, 1
            s = "".join("1" if v else "0" for v in line)
            for pat in ("10111010000", "00001011101"):
                start = s.find(pat)
                while start != -1:
                    result += 40
                    start = s.find(pat, start + 1)
        for y in range(size - 1):
            for x in range(size - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    result += 3
        dark = sum(v for row in m for v in row)
        total = size * size
        k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
        return result + k * 10

    # ------------------------------------------------------------ output
    def to_text(self, border: int = 2) -> str:
        """Two rows per line with half blocks, dark on light (works on most terminals)."""
        size = self.size
        get = lambda x, y: 0 <= x < size and 0 <= y < size and self.modules[y][x]  # noqa: E731
        out = []
        for y in range(-border, size + border, 2):
            row = []
            for x in range(-border, size + border):
                top, bottom = get(x, y), get(x, y + 1)
                row.append({(False, False): "█", (True, False): "▄",
                            (False, True): "▀", (True, True): " "}[(top, bottom)])
            out.append("".join(row))
        return "\n".join(out)

    def to_svg(self, border: int = 4, scale: int = 8) -> str:
        n = self.size + 2 * border
        parts = [f"M{x + border},{y + border}h1v1h-1z" for y in range(self.size)
                 for x in range(self.size) if self.modules[y][x]]
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
                f'width="{n * scale}" height="{n * scale}" shape-rendering="crispEdges">'
                f'<rect width="100%" height="100%" fill="#fff"/>'
                f'<path d="{" ".join(parts)}" fill="#000"/></svg>\n')


def encode(text: str, ecl: int = ECC_M) -> QrCode:
    data = text.encode("utf-8")
    for ver in range(1, 41):
        count_bits = 8 if ver < 10 else 16
        used = 4 + count_bits + 8 * len(data)
        cap = _data_codewords(ver, ecl) * 8
        if used <= cap:
            break
    else:
        raise ValueError("text too long for a QR code")
    bits: list[int] = []

    def put(val: int, n: int) -> None:
        bits.extend((val >> i) & 1 for i in reversed(range(n)))

    put(0b0100, 4)
    put(len(data), count_bits)
    for b in data:
        put(b, 8)
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(codewords) < cap // 8:
        codewords.append(pad)
        pad ^= 0xEC ^ 0x11
    return QrCode(ver, ecl, codewords)
