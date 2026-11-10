"""由 assets/icon.png 產生 assets/icon.ico（右鍵選單的 Icon 只支援 .ico／exe／dll，不支援 PNG）。

修改 icon.png 後執行一次：py -3 scripts\\make_icon.py，並把產生的 icon.ico 一併保留。
需要 opencv-python 與 numpy（requirements.txt）。ICO 內每個尺寸都以 PNG 編碼（Vista 以上支援）。
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icon.png"
OUTPUT = ROOT / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def build_ico(png_images: list[tuple[int, bytes]]) -> bytes:
	header = struct.pack("<HHH", 0, 1, len(png_images))
	offset = 6 + 16 * len(png_images)
	entries = b""
	payload = b""
	for size, data in png_images:
		dimension = 0 if size >= 256 else size  # ICO 以 0 代表 256
		entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset + len(payload))
		payload += data
	return header + entries + payload


def main() -> int:
	import cv2
	import numpy as np

	image = cv2.imread(str(SOURCE), cv2.IMREAD_UNCHANGED)
	if image is None:
		print(f"無法讀取：{SOURCE}", file=sys.stderr)
		return 1
	if image.ndim == 2:
		image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
	elif image.shape[2] == 3:
		image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

	height, width = image.shape[:2]
	side = max(width, height)
	square = np.zeros((side, side, 4), dtype=np.uint8)  # 透明底，圖案置中
	top, left = (side - height) // 2, (side - width) // 2
	square[top:top + height, left:left + width] = image

	png_images = []
	for size in SIZES:
		resized = cv2.resize(square, (size, size), interpolation=cv2.INTER_AREA)
		ok, encoded = cv2.imencode(".png", resized)
		if not ok:
			print(f"PNG 編碼失敗（{size}px）", file=sys.stderr)
			return 1
		png_images.append((size, encoded.tobytes()))

	OUTPUT.write_bytes(build_ico(png_images))
	print(f"已建立：{OUTPUT}（{', '.join(str(s) for s in SIZES)} px）")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
