"""從檔案總管右鍵選單啟動時的執行階段（wkt --from-menu <工具> <檔案>）。

要解決的兩個問題：

1. 多選 N 個檔案按右鍵，Explorer 會為每個檔案各啟動一個程序（N 個視窗）。
   做法：每個程序先把自己的檔案寫進佇列資料夾，再搶「領導者鎖」；
   搶到的人等一小段時間收集其他程序的檔案，統一批次處理；沒搶到的人直接結束。
2. 視窗跑完就消失，使用者看不到結果。
   做法：全部成功時顯示結果數秒後自動關閉；有失敗時停住等使用者按 Enter。

鎖使用 msvcrt.locking：程序結束（即使當機）時由作業系統自動釋放，不會留下過期的鎖。
"""

from __future__ import annotations

import argparse
import copy
import os
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from wkt.batch import run_batch
from wkt.core.errors import WktError


COLLECT_SECONDS = 0.5  # 領導者等待其他程序登記檔案的時間
SUCCESS_LINGER_SECONDS = 3.0  # 全部成功時，結果畫面停留的時間
LOCK_NAME = "leader.lock"
JOB_SUFFIX = ".job"


def queue_root() -> Path:
	base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
	return Path(base) / "WKT" / "queue"


def enqueue(queue_dir: Path, paths: list[str]) -> Path:
	"""把檔案清單寫成一個工作檔；先寫暫存檔再改名，領導者不會讀到寫一半的內容。"""
	queue_dir.mkdir(parents=True, exist_ok=True)
	name = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
	temp_path = queue_dir / f"{name}.tmp"
	temp_path.write_text("\n".join(paths), encoding="utf-8")
	job_path = queue_dir / f"{name}{JOB_SUFFIX}"
	temp_path.replace(job_path)
	return job_path


def drain(queue_dir: Path) -> list[str]:
	"""取出佇列中所有工作檔的檔案（依登記順序），並刪除工作檔。"""
	paths: list[str] = []
	for job in sorted(queue_dir.glob(f"*{JOB_SUFFIX}")):
		try:
			lines = job.read_text(encoding="utf-8").splitlines()
			job.unlink()
		except OSError:
			continue
		paths.extend(line for line in lines if line)
	return paths


def try_lock(queue_dir: Path) -> int | None:
	"""嘗試取得領導者鎖；已被別人持有回傳 None。"""
	import msvcrt

	queue_dir.mkdir(parents=True, exist_ok=True)
	fd = os.open(queue_dir / LOCK_NAME, os.O_CREAT | os.O_RDWR)
	try:
		msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
	except OSError:
		os.close(fd)
		return None
	return fd


def unlock(fd: int) -> None:
	import msvcrt

	try:
		os.lseek(fd, 0, os.SEEK_SET)
		msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
	finally:
		os.close(fd)


def pause_for_user() -> None:
	try:
		input("\n按 Enter 鍵關閉……")
	except (EOFError, KeyboardInterrupt):
		pass


def process_queue(
	queue_dir: Path,
	run: Callable[[argparse.Namespace], None],
	args: argparse.Namespace,
	collect_seconds: float = COLLECT_SECONDS,
) -> bool | None:
	"""領導者的工作迴圈。回傳是否全部成功；一次都沒搶到鎖（別人是領導者）回傳 None。

	處理完後放開鎖，再檢查一次佇列：處理期間才登記、且搶鎖失敗的程序，
	它們的檔案不會被漏掉（登記一定發生在搶鎖之前）。
	"""
	all_ok = True
	led = False
	while True:
		fd = try_lock(queue_dir)
		if fd is None:
			return all_ok if led else None  # 別人接手了
		led = True
		try:
			time.sleep(collect_seconds)
			paths = drain(queue_dir)
			while paths:
				batch_args = copy.copy(args)
				batch_args.input = paths
				try:
					if run_batch(run, batch_args) != 0:
						all_ok = False
				except WktError as exc:
					print(exc.message)
					all_ok = False
				except Exception as exc:  # 視窗不能直接關掉，使用者才看得到原因
					print(f"處理失敗：{exc}")
					all_ok = False
				paths = drain(queue_dir)
		finally:
			unlock(fd)
		if not any(queue_dir.glob(f"*{JOB_SUFFIX}")):
			return all_ok


def run_from_menu(
	run: Callable[[argparse.Namespace], None],
	args: argparse.Namespace,
	tool_name: str,
	*,
	collect_seconds: float = COLLECT_SECONDS,
	linger_seconds: float = SUCCESS_LINGER_SECONDS,
) -> int:
	"""右鍵選單的進入點；回傳結束碼。"""
	queue_dir = queue_root() / tool_name
	enqueue(queue_dir, list(args.input))
	all_ok = process_queue(queue_dir, run, args, collect_seconds)
	if all_ok is None:
		return 0  # 已有領導者在處理，這個視窗不需要做事
	if all_ok:
		print(f"\n全部完成，{linger_seconds:g} 秒後自動關閉……")
		time.sleep(linger_seconds)
		return 0
	pause_for_user()
	return 1
