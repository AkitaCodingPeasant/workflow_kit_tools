"""參數預設組（profile）：把一組參數值當成「預設值的覆寫層」。

優先順序：命令列明確指定的參數 > --profile > 內建預設組。
使用前提：被管理的參數在 argparse 中的 default 必須是 None，才分得出「沒輸入」與「輸入了預設值」。
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping


def apply_profile(
	args: argparse.Namespace,
	profiles: Mapping[str, Mapping[str, object]],
	default: str,
) -> None:
	"""把選定（或預設）的 profile 補進 args 中仍是 None 的欄位。"""
	name = getattr(args, "profile", None) or default
	for key, value in profiles[name].items():
		if getattr(args, key, None) is None:
			setattr(args, key, value)


def describe_profiles(profiles: Mapping[str, Mapping[str, object]], default: str) -> str:
	"""給 -h 說明用的預設組清單，例如：small: fps=8 width=320 colors=64。"""
	lines = []
	for name, values in profiles.items():
		detail = " ".join(f"{key}={value}" for key, value in values.items())
		suffix = "（預設）" if name == default else ""
		lines.append(f"  {name:<9}{detail}{suffix}")
	return "\n".join(lines)
