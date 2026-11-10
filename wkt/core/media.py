"""以 OpenCV 逐幀處理圖片／影片的共用流程。

OpenCV 與 numpy 一律在函式內才 import（見 load_cv2），
這樣沒用到它們的工具與 `wkt --help` 不需要安裝這兩個套件。
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wkt.core.errors import WktError
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


Size = tuple[int, int]  # (寬, 高)
FrameFunc = Callable[[Any], Any]  # 輸入一幀 ndarray，回傳處理後的 ndarray

MEDIA_TYPES = ("auto", "image", "video")
DEFAULT_FPS = 30.0
INSTALL_HINT = "缺少 {name}，請執行：pip install -r requirements.txt"


def load_cv2() -> Any:
	try:
		import cv2
	except ImportError as exc:
		raise WktError(INSTALL_HINT.format(name="opencv-python")) from exc
	return cv2


def load_numpy() -> Any:
	try:
		import numpy
	except ImportError as exc:
		raise WktError(INSTALL_HINT.format(name="numpy")) from exc
	return numpy


def detect_media_type(input_path: Path) -> str:
	"""能被 cv2.imread 讀取就是 image；能被 VideoCapture 開啟就是 video。"""
	cv2 = load_cv2()
	if cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED) is not None:
		return "image"

	capture = cv2.VideoCapture(str(input_path))
	try:
		if capture.isOpened():
			return "video"
	finally:
		capture.release()

	raise WktError(f"無法判斷媒體類型：{input_path}")


def _pick_video_fourcc(output_path: Path) -> int:
	cv2 = load_cv2()
	if output_path.suffix.lower() == ".avi":
		return cv2.VideoWriter_fourcc(*"XVID")
	return cv2.VideoWriter_fourcc(*"mp4v")


def _check_size(width: int, height: int, expected: Size, label: str) -> None:
	if (width, height) != expected:
		raise WktError(f"{label}尺寸必須是 {expected[0]}x{expected[1]}，目前是 {width}x{height}")


def transform_image(input_path: Path, output_path: Path, frame_fn: FrameFunc, expected_size: Size) -> None:
	cv2 = load_cv2()
	image = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
	if image is None:
		raise WktError(f"無法讀取圖片：{input_path}")

	height, width = image.shape[:2]
	_check_size(width, height, expected_size, "輸入")
	if not cv2.imwrite(str(output_path), frame_fn(image)):
		raise WktError(f"無法寫出圖片：{output_path}")


def transform_video(
	input_path: Path,
	output_path: Path,
	frame_fn: FrameFunc,
	expected_size: Size,
	output_size: Size,
) -> None:
	cv2 = load_cv2()
	capture = cv2.VideoCapture(str(input_path))
	if not capture.isOpened():
		raise WktError(f"無法開啟影片：{input_path}")

	writer = None
	try:
		width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
		height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
		_check_size(width, height, expected_size, "影片")

		fps = capture.get(cv2.CAP_PROP_FPS)
		if not fps or fps <= 0:
			fps = DEFAULT_FPS

		writer = cv2.VideoWriter(str(output_path), _pick_video_fourcc(output_path), fps, output_size)
		if not writer.isOpened():
			raise WktError(f"無法建立輸出影片：{output_path}")

		while True:
			ok, frame = capture.read()
			if not ok:
				break
			writer.write(frame_fn(frame))
	finally:
		capture.release()
		if writer is not None:
			writer.release()


def add_media_arguments(parser: argparse.ArgumentParser, tag: str) -> None:
	"""圖片／影片逐幀工具共用的參數：input、-o、--type。"""
	parser.add_argument("input", help="輸入圖片或影片路徑")
	parser.add_argument("-o", "--output", help=f"輸出路徑；未指定時會自動加上 _{tag}")
	parser.add_argument("--type", choices=MEDIA_TYPES, default="auto", help="指定媒體類型，預設 auto")


def run_frame_tool(
	args: argparse.Namespace,
	*,
	tag: str,
	frame_fn: FrameFunc,
	expected_size: Size,
	output_size: Size,
) -> None:
	"""圖片／影片逐幀工具的完整流程：驗證 → 判斷類型 → 逐幀處理 → 回報。"""
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, tag=tag)
	ensure_not_same(input_path, output_path)

	media_type = args.type
	if media_type == "auto":
		media_type = detect_media_type(input_path)

	if media_type == "image":
		transform_image(input_path, output_path, frame_fn, expected_size)
	else:
		transform_video(input_path, output_path, frame_fn, expected_size, output_size)

	print(f"完成：{output_path}")
