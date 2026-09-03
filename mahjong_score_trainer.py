"""
日麻点数计算训练器（雀魂四人麻将规则）

特点：
1. 只使用 Python 标准库，不需要安装第三方包；
2. 使用同一套高清 PNG 麻将牌素材，图形界面仍只依赖 tkinter；
3. 覆盖 1～13 番、亲家/子家、荣和/自摸；
4. 每题有 5 秒计时，但超时后仍可继续输入答案；
5. 每 10 题分别统计答案正确率和 5 秒内答对率。

运行方式：
    Windows:    py mahjong_score_trainer.py
    macOS/Linux: python3 mahjong_score_trainer.py

只运行内置自检：
    py mahjong_score_trainer.py --self-test
"""

from __future__ import annotations

import random
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# tkinter 属于 Python 标准库。某些精简版 Linux Python 可能没有安装 Tk，
# 因此这里捕获导入错误，并在 main() 中输出易懂的提示。
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError as exc:  # pragma: no cover - 仅在系统缺少 Tk 时执行
    tk = None  # type: ignore
    messagebox = None  # type: ignore
    TK_IMPORT_ERROR = exc
else:
    TK_IMPORT_ERROR = None


# ---------------------------------------------------------------------------
# 一、点数表与计分函数
# ---------------------------------------------------------------------------

# 用户指定的子家荣和表。None 表示牌理上不存在的组合：
# - 20 符只会出现在平和自摸，荣和不可能仍是 20 符；
# - 25 符来自七对子，而七对子本身至少 2 番。
CHILD_RON_TABLE: Dict[int, Dict[int, Optional[int]]] = {
    20: {1: None, 2: None, 3: None, 4: None},
    25: {1: None, 2: 1600, 3: 3200, 4: 6400},
    30: {1: 1000, 2: 2000, 3: 3900, 4: 7700},
    40: {1: 1300, 2: 2600, 3: 5200, 4: 8000},
    50: {1: 1600, 2: 3200, 3: 6400, 4: 8000},
    70: {1: 2300, 2: 4500, 3: 8000, 4: 8000},
}

FU_VALUES: Tuple[int, ...] = tuple(CHILD_RON_TABLE.keys())
NORMAL_HAN_VALUES: Tuple[int, ...] = (1, 2, 3, 4)


def round_up_100(points: int) -> int:
    """将点数向上取整到百位，例如 3360 -> 3400。"""

    return ((points + 99) // 100) * 100


def round_up_10(fu: int) -> int:
    """将符数向上取整到十位；七对子 25 符等特殊情况不使用此函数。"""

    return ((fu + 9) // 10) * 10


def calculate_base_points(fu: int, han: int) -> int:
    """
    计算 1～4 番手牌的基本点。

    通常公式为：符 × 2 ** (番数 + 2)。
    当结果达到 2000 基本点时按满贯封顶，因此 4 番 40 符、
    3 番 70 符等都会得到 2000 基本点。
    """

    if fu not in FU_VALUES:
        raise ValueError("符数必须是 20、25、30、40、50 或 70")
    if han not in NORMAL_HAN_VALUES:
        raise ValueError("calculate_base_points 只处理 1～4 番")
    return min(fu * (2 ** (han + 2)), 2000)


def limit_base_points(han: int) -> int:
    """返回 5～13 番限制点手牌的基本点。"""

    if han == 5:                 # 满贯
        return 2000
    if 6 <= han <= 7:            # 跳满
        return 3000
    if 8 <= han <= 10:           # 倍满
        return 4000
    if 11 <= han <= 12:          # 三倍满
        return 6000
    if han == 13:                # 累计役满
        return 8000
    raise ValueError("限制点番数必须在 5～13 之间")


def generate_dealer_ron_table() -> Dict[int, Dict[int, Optional[int]]]:
    """
    自动生成亲家荣和表。

    注意：不能把“已经向百位进位的子家点数”直接乘 1.5，否则会把
    30 符 3 番错误算成 5900。正确做法是用未进位基本点乘 6，
    最后只进行一次百位进位。
    """

    table: Dict[int, Dict[int, Optional[int]]] = {}
    for fu, row in CHILD_RON_TABLE.items():
        table[fu] = {}
        for han, child_score in row.items():
            if child_score is None:
                table[fu][han] = None
            else:
                base = calculate_base_points(fu, han)
                table[fu][han] = round_up_100(base * 6)
    return table


DEALER_RON_TABLE = generate_dealer_ron_table()


def calculate_tsumo(is_dealer: bool, fu: int, han: int) -> Tuple[int, ...]:
    """
    计算自摸时每家的支付额。

    返回值约定：
    - 亲家自摸：返回 (每名子家支付额,)
    - 子家自摸：返回 (每名子家支付额, 亲家支付额)

    对 5 番以上的限制点，fu 仅用于保留题目的真实符数，不影响点数。
    """

    if 1 <= han <= 4:
        base = calculate_base_points(fu, han)
    elif 5 <= han <= 13:
        base = limit_base_points(han)
    else:
        raise ValueError("番数必须在 1～13 之间")

    if is_dealer:
        return (round_up_100(base * 2),)
    return (round_up_100(base), round_up_100(base * 2))


def calculate_limit_score(is_dealer: bool, win_type: str, han: int) -> Tuple[int, ...]:
    """计算 5～13 番的荣和或自摸点数。"""

    base = limit_base_points(han)
    if win_type == "ron":
        multiplier = 6 if is_dealer else 4
        return (round_up_100(base * multiplier),)
    if win_type == "tsumo":
        # fu 在限制点中不参与计算，这里传入任一支持的符数即可。
        return calculate_tsumo(is_dealer, 30, han)
    raise ValueError("win_type 必须是 'ron' 或 'tsumo'")


def calculate_score(is_dealer: bool, win_type: str, fu: int, han: int) -> Tuple[int, ...]:
    """亲家/子家、荣和/自摸共用的统一计分入口。"""

    if 5 <= han <= 13:
        return calculate_limit_score(is_dealer, win_type, han)

    if win_type == "tsumo":
        if not is_valid_normal_combo(win_type, fu, han):
            raise ValueError("这是牌理上不存在的符番组合")
        return calculate_tsumo(is_dealer, fu, han)

    if win_type == "ron":
        table = DEALER_RON_TABLE if is_dealer else CHILD_RON_TABLE
        score = table[fu][han]
        if score is None:
            raise ValueError("这是牌理上不存在的荣和组合")
        return (score,)

    raise ValueError("win_type 必须是 'ron' 或 'tsumo'")


def limit_name(han: int) -> str:
    """把番数转换为满贯以上的中文档位名称。"""

    if han == 5:
        return "满贯"
    if 6 <= han <= 7:
        return "跳满"
    if 8 <= han <= 10:
        return "倍满"
    if 11 <= han <= 12:
        return "三倍满"
    if han == 13:
        return "累计役满"
    return "普通手"


def is_valid_normal_combo(win_type: str, fu: int, han: int) -> bool:
    """判断 1～4 番的符番组合是否能在实战中出现。"""

    if fu not in FU_VALUES or han not in NORMAL_HAN_VALUES:
        return False
    if win_type == "ron":
        return CHILD_RON_TABLE[fu][han] is not None
    if win_type == "tsumo":
        # 平和自摸至少是 20 符 2 番；七对子自摸至少是 25 符 3 番。
        if fu == 20:
            return han >= 2
        if fu == 25:
            return han >= 3
        return True
    return False


# ---------------------------------------------------------------------------
# 二、牌型模板与宝牌控制
# ---------------------------------------------------------------------------

# 牌编码约定：1m～9m 为万子，1p～9p 为筒子，1s～9s 为索子；
# E/S/W/N 为东南西北，P/F/C 为白发中。
NUMBER_TILES: Tuple[str, ...] = tuple(
    "{}{}".format(rank, suit)
    for suit in ("m", "p", "s")
    for rank in range(1, 10)
)
HONOR_TILES: Tuple[str, ...] = ("E", "S", "W", "N", "P", "F", "C")
ALL_TILES: Tuple[str, ...] = NUMBER_TILES + HONOR_TILES


@dataclass(frozen=True)
class TileGroup:
    """一个顺子、刻子、杠子或对子。"""

    tiles: Tuple[str, ...]
    kind: str                 # sequence / triplet / kan / pair
    is_open: bool = False     # 是否为副露面子


@dataclass(frozen=True)
class HandTemplate:
    """一副已经完成、且符番经过人工核对的和牌模板。"""

    key: str
    title: str
    family: str              # normal 或 high
    win_type: str            # ron 或 tsumo
    groups: Tuple[TileGroup, ...]
    win_group: int           # 和牌张所在组
    win_index: int           # 和牌张在组内的位置
    fu: int
    fu_items: Tuple[Tuple[str, int], ...]
    fixed_fu: bool           # 平和自摸 20 符、七对子 25 符为固定符
    base_han: int
    yaku: Tuple[Tuple[str, int], ...]
    max_bonus: int
    bonus_strategy: str = "indicator"  # indicator 或 red_plus_pair
    aka_tile: Optional[str] = None


@dataclass(frozen=True)
class BonusPlan:
    """为了把基础牌型补到目标番数而选择的宝牌方案。"""

    indicator: str
    dora_tile: str
    visible_dora_count: int
    aka_tile: Optional[str]

    @property
    def total_bonus_han(self) -> int:
        return self.visible_dora_count + (1 if self.aka_tile else 0)


@dataclass(frozen=True)
class Question:
    """界面显示和判题所需的完整题目。"""

    is_dealer: bool
    win_type: str
    fu: int
    han: int
    tier: str
    template: HandTemplate
    bonus: BonusPlan
    expected: Tuple[int, ...]


def group(tiles: Sequence[str], kind: str, is_open: bool = False) -> TileGroup:
    """简化模板声明的小工具。"""

    return TileGroup(tuple(tiles), kind, is_open)


def hand_tiles(template: HandTemplate) -> List[str]:
    """把模板的所有牌摊平成一个列表。杠子会保留第 4 张牌。"""

    return [tile for tile_group in template.groups for tile in tile_group.tiles]


def previous_dora_indicator(dora_tile: str) -> str:
    """给定宝牌，返回能指向它的宝牌指示牌。"""

    if len(dora_tile) == 2:
        rank = int(dora_tile[0])
        suit = dora_tile[1]
        previous_rank = 9 if rank == 1 else rank - 1
        return "{}{}".format(previous_rank, suit)

    wind_cycle = ("E", "S", "W", "N")
    dragon_cycle = ("P", "F", "C")
    if dora_tile in wind_cycle:
        index = wind_cycle.index(dora_tile)
        return wind_cycle[index - 1]
    if dora_tile in dragon_cycle:
        index = dragon_cycle.index(dora_tile)
        return dragon_cycle[index - 1]
    raise ValueError("未知牌编码：{}".format(dora_tile))


def dora_from_indicator(indicator: str) -> str:
    """给定指示牌，返回实际宝牌。主要用于自检和答案解析。"""

    if len(indicator) == 2:
        rank = int(indicator[0])
        suit = indicator[1]
        next_rank = 1 if rank == 9 else rank + 1
        return "{}{}".format(next_rank, suit)

    wind_cycle = ("E", "S", "W", "N")
    dragon_cycle = ("P", "F", "C")
    if indicator in wind_cycle:
        return wind_cycle[(wind_cycle.index(indicator) + 1) % len(wind_cycle)]
    if indicator in dragon_cycle:
        return dragon_cycle[(dragon_cycle.index(indicator) + 1) % len(dragon_cycle)]
    raise ValueError("未知指示牌：{}".format(indicator))


def _find_indicator_with_count(template: HandTemplate, target_count: int) -> Tuple[str, str]:
    """寻找一张指示牌，使其宝牌在手中恰好出现 target_count 次。"""

    counts = Counter(hand_tiles(template))
    for dora_tile in ALL_TILES:
        if counts[dora_tile] != target_count:
            continue
        indicator = previous_dora_indicator(dora_tile)
        # 指示牌来自牌山；若同牌已经 4 张全在手中，就不能再拿一张做指示牌。
        if counts[indicator] < 4:
            return indicator, dora_tile
    raise ValueError(
        "模板 {} 找不到能产生 {} 枚宝牌的指示牌".format(template.key, target_count)
    )


def choose_bonus_plan(template: HandTemplate, needed_han: int) -> BonusPlan:
    """
    为模板选择严格匹配的宝牌方案。

    普通模板通过一张指示牌让目标牌出现 0～3 次。
    七对子和二杯口模板中的牌张计数都是偶数，因此需要奇数番时使用
    一张赤五，再用指示牌补 0 或 2 番。
    """

    if not 0 <= needed_han <= template.max_bonus:
        raise ValueError("模板无法补足所需宝牌番数")

    aka_tile: Optional[str] = None
    visible_count = needed_han
    if template.bonus_strategy == "red_plus_pair":
        if needed_han % 2 == 1:
            if template.aka_tile is None:
                raise ValueError("赤宝牌策略缺少 aka_tile")
            aka_tile = template.aka_tile
            visible_count -= 1
        if visible_count not in (0, 2):
            raise ValueError("赤宝牌策略只能组合出 0～3 番")

    indicator, dora_tile = _find_indicator_with_count(template, visible_count)
    return BonusPlan(indicator, dora_tile, visible_count, aka_tile)


def build_templates() -> Tuple[HandTemplate, ...]:
    """创建所有普通题和高番题使用的合法牌型模板。"""

    templates: List[HandTemplate] = []

    # ---- 20 符：平和自摸固定 20 符，基础 2 番。 ----
    pinfu_20_groups = (
        group(("1m", "2m", "3m"), "sequence"),
        group(("3m", "4m", "5m"), "sequence"),
        group(("5m", "6m", "7m"), "sequence"),
        group(("7p", "8p", "9p"), "sequence"),
        group(("2s", "2s"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_20_tsumo", "平和自摸", "normal", "tsumo",
        pinfu_20_groups, 1, 0, 20, (("平和自摸固定", 20),), True,
        2, (("平和", 1), ("门前清自摸和", 1)), 2,
    ))

    # ---- 25 符：七对子固定 25 符。 ----
    chiitoi_groups = (
        group(("1m", "1m"), "pair"),
        group(("2m", "2m"), "pair"),
        group(("4p", "4p"), "pair"),
        group(("5p", "5p"), "pair"),
        group(("6s", "6s"), "pair"),
        group(("E", "E"), "pair"),
        group(("P", "P"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_25_ron", "七对子荣和", "normal", "ron",
        chiitoi_groups, 0, 1, 25, (("七对子固定", 25),), True,
        2, (("七对子", 2),), 2, "red_plus_pair", "5p",
    ))
    templates.append(HandTemplate(
        "normal_25_tsumo", "七对子自摸", "normal", "tsumo",
        chiitoi_groups, 0, 1, 25, (("七对子固定", 25),), True,
        3, (("七对子", 2), ("门前清自摸和", 1)), 1,
        "red_plus_pair", "5p",
    ))

    # ---- 30 符荣和：门清平和荣和为 30 符，基础 1 番。 ----
    pinfu_30_groups = (
        group(("2m", "3m", "4m"), "sequence"),
        group(("3m", "4m", "5m"), "sequence"),
        group(("4m", "5m", "6m"), "sequence"),
        group(("7p", "8p", "9p"), "sequence"),
        group(("2s", "2s"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_30_ron", "平和荣和", "normal", "ron",
        pinfu_30_groups, 0, 0, 30,
        (("副底", 20), ("门清荣和", 10)), False,
        1, (("平和", 1),), 3,
    ))

    # ---- 30 符自摸：副底 20 + 自摸 2 + 役牌雀头 2 = 24，进位为 30。 ----
    normal_30_tsumo_groups = (
        group(("2m", "3m", "4m"), "sequence"),
        group(("3m", "4m", "5m"), "sequence"),
        group(("4m", "5m", "6m"), "sequence"),
        group(("7p", "8p", "9p"), "sequence"),
        group(("P", "P"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_30_tsumo", "门清自摸", "normal", "tsumo",
        normal_30_tsumo_groups, 0, 0, 30,
        (("副底", 20), ("自摸", 2), ("役牌雀头", 2)), False,
        1, (("门前清自摸和", 1),), 3,
    ))

    # ---- 40 符荣和：副底 20 + 门清荣和 10 + 暗刻幺九字牌 8 = 38。 ----
    normal_40_ron_groups = (
        group(("P", "P", "P"), "triplet"),
        group(("2m", "3m", "4m"), "sequence"),
        group(("5p", "6p", "7p"), "sequence"),
        group(("7s", "8s", "9s"), "sequence"),
        group(("2p", "2p"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_40_ron", "役牌暗刻荣和", "normal", "ron",
        normal_40_ron_groups, 1, 0, 40,
        (("副底", 20), ("门清荣和", 10), ("幺九字牌暗刻", 8)), False,
        1, (("役牌·白", 1),), 3,
    ))

    # ---- 40 符自摸：20 + 自摸 2 + 幺九暗刻 8 + 役牌雀头 2 = 32。 ----
    normal_40_tsumo_groups = (
        group(("1m", "1m", "1m"), "triplet"),
        group(("2p", "3p", "4p"), "sequence"),
        group(("5s", "6s", "7s"), "sequence"),
        group(("7m", "8m", "9m"), "sequence"),
        group(("P", "P"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_40_tsumo", "幺九暗刻自摸", "normal", "tsumo",
        normal_40_tsumo_groups, 1, 0, 40,
        (("副底", 20), ("自摸", 2), ("幺九牌暗刻", 8), ("役牌雀头", 2)), False,
        1, (("门前清自摸和", 1),), 3,
    ))

    # ---- 50 符：暗杠中张 16 + 暗刻中张 4。 ----
    normal_50_groups = (
        group(("5m", "5m", "5m", "5m"), "kan"),
        group(("6p", "6p", "6p"), "triplet"),
        group(("1s", "2s", "3s"), "sequence"),
        group(("7m", "8m", "9m"), "sequence"),
        group(("2p", "2p"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_50_ron", "立直暗杠荣和", "normal", "ron",
        normal_50_groups, 2, 0, 50,
        (("副底", 20), ("门清荣和", 10), ("中张暗杠", 16), ("中张暗刻", 4)), False,
        1, (("立直", 1),), 3,
    ))
    templates.append(HandTemplate(
        "normal_50_tsumo", "暗杠自摸", "normal", "tsumo",
        normal_50_groups, 2, 0, 50,
        (("副底", 20), ("自摸", 2), ("中张暗杠", 16), ("中张暗刻", 4)), False,
        1, (("门前清自摸和", 1),), 3,
    ))

    # ---- 70 符荣和：字牌暗杠 32 + 中张暗刻 4，合计 66 后进位。 ----
    normal_70_ron_groups = (
        group(("P", "P", "P", "P"), "kan"),
        group(("6p", "6p", "6p"), "triplet"),
        group(("1s", "2s", "3s"), "sequence"),
        group(("7m", "8m", "9m"), "sequence"),
        group(("2p", "2p"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_70_ron", "役牌暗杠荣和", "normal", "ron",
        normal_70_ron_groups, 2, 0, 70,
        (("副底", 20), ("门清荣和", 10), ("字牌暗杠", 32), ("中张暗刻", 4)), False,
        1, (("役牌·白", 1),), 3,
    ))

    # ---- 70 符自摸：幺九暗杠 32 + 幺九暗刻 8，合计 62 后进位。 ----
    normal_70_tsumo_groups = (
        group(("1m", "1m", "1m", "1m"), "kan"),
        group(("9p", "9p", "9p"), "triplet"),
        group(("2s", "3s", "4s"), "sequence"),
        group(("5m", "6m", "7m"), "sequence"),
        group(("2p", "2p"), "pair"),
    )
    templates.append(HandTemplate(
        "normal_70_tsumo", "幺九暗杠自摸", "normal", "tsumo",
        normal_70_tsumo_groups, 2, 0, 70,
        (("副底", 20), ("自摸", 2), ("幺九牌暗杠", 32), ("幺九牌暗刻", 8)), False,
        1, (("门前清自摸和", 1),), 3,
    ))

    # ---- 高番模板 A：副露清一色，基础 5 番，荣和/自摸都可使用。 ----
    high_open_groups = (
        group(("1m", "2m", "3m"), "sequence", True),
        group(("3m", "4m", "5m"), "sequence"),
        group(("5m", "6m", "7m"), "sequence"),
        group(("9m", "9m", "9m"), "triplet"),
        group(("2m", "2m"), "pair"),
    )
    templates.append(HandTemplate(
        "high_open_ron", "副露清一色荣和", "high", "ron",
        high_open_groups, 1, 0, 30,
        (("副底", 20), ("幺九牌暗刻", 8)), False,
        5, (("清一色（副露）", 5),), 3,
    ))
    templates.append(HandTemplate(
        "high_open_tsumo", "副露清一色自摸", "high", "tsumo",
        high_open_groups, 1, 0, 30,
        (("副底", 20), ("自摸", 2), ("幺九牌暗刻", 8)), False,
        5, (("清一色（副露）", 5),), 3,
    ))

    # ---- 高番模板 B：门清清一色，荣和 6 番，自摸增加门清自摸 1 番。 ----
    high_closed_groups = tuple(
        TileGroup(item.tiles, item.kind, False) for item in high_open_groups
    )
    templates.append(HandTemplate(
        "high_closed_ron", "门清清一色荣和", "high", "ron",
        high_closed_groups, 1, 0, 40,
        (("副底", 20), ("门清荣和", 10), ("幺九牌暗刻", 8)), False,
        6, (("清一色（门清）", 6),), 3,
    ))
    templates.append(HandTemplate(
        "high_closed_tsumo", "门清清一色自摸", "high", "tsumo",
        high_closed_groups, 1, 0, 30,
        (("副底", 20), ("自摸", 2), ("幺九牌暗刻", 8)), False,
        7, (("清一色（门清）", 6), ("门前清自摸和", 1)), 3,
    ))

    # ---- 高番模板 C：清一色 + 二杯口 + 平和。 ----
    # 使用 123m×2、678m×2、55m。包含幺九牌，所以不会额外形成断幺九。
    # 所有普通牌都恰好出现 2 张；需要奇数宝牌时把一张 5m 设为赤五。
    high_ryanpeikou_groups = (
        group(("1m", "2m", "3m"), "sequence"),
        group(("1m", "2m", "3m"), "sequence"),
        group(("6m", "7m", "8m"), "sequence"),
        group(("6m", "7m", "8m"), "sequence"),
        group(("5m", "5m"), "pair"),
    )
    templates.append(HandTemplate(
        "high_ryanpeikou_ron", "清一色二杯口荣和", "high", "ron",
        high_ryanpeikou_groups, 2, 0, 30,
        (("副底", 20), ("门清荣和", 10)), False,
        10, (("清一色（门清）", 6), ("二杯口", 3), ("平和", 1)), 3,
        "red_plus_pair", "5m",
    ))
    templates.append(HandTemplate(
        "high_ryanpeikou_tsumo", "清一色二杯口自摸", "high", "tsumo",
        high_ryanpeikou_groups, 2, 0, 20,
        (("平和自摸固定", 20),), True,
        11,
        (("清一色（门清）", 6), ("二杯口", 3), ("平和", 1), ("门前清自摸和", 1)),
        2, "red_plus_pair", "5m",
    ))

    return tuple(templates)


HAND_TEMPLATES: Tuple[HandTemplate, ...] = build_templates()


# ---------------------------------------------------------------------------
# 三、加权随机出题
# ---------------------------------------------------------------------------

# 权重直接以“全部题目的百分比”表示，总和为 100。
QUESTION_BUCKETS: Tuple[str, ...] = (
    "normal", "mangan", "haneman", "baiman", "sanbaiman", "kazoe"
)
QUESTION_WEIGHTS: Tuple[float, ...] = (80.0, 7.0, 7.0, 3.0, 2.0, 1.0)

# 普通题先按符数抽取，再从该符数的有效番数中抽取。30、40 符在实战中
# 最常见，因此占主要权重；70 符仍会出现，但只保留少量练习机会。
# 荣和不存在 20 符时，会自动在其余有效符数之间按比例重新归一化。
NORMAL_FU_WEIGHTS: Dict[int, float] = {
    20: 12.0,
    25: 8.0,
    30: 42.0,
    40: 26.0,
    50: 10.0,
    70: 2.0,
}

# 同一符数下番数通常等权；1 番 70 符属于尤其少见的组合，再降为四分之一权重。
NORMAL_COMBO_WEIGHT_OVERRIDES: Dict[Tuple[int, int], float] = {
    (70, 1): 0.25,
}

BUCKET_HAN: Dict[str, Tuple[int, ...]] = {
    "mangan": (5,),
    "haneman": (6, 7),
    "baiman": (8, 9, 10),
    "sanbaiman": (11, 12),
    "kazoe": (13,),
}


def choose_question_bucket(rng: random.Random) -> str:
    """按 80/7/7/3/2/1 权重选择普通题或限制点档位。"""

    return rng.choices(QUESTION_BUCKETS, weights=QUESTION_WEIGHTS, k=1)[0]


def choose_normal_combo(win_type: str, rng: random.Random) -> Tuple[int, int]:
    """按常见度选择有效的普通题符数，再选择对应番数。"""

    valid_fu_values = [
        fu for fu in FU_VALUES
        if any(is_valid_normal_combo(win_type, fu, han) for han in NORMAL_HAN_VALUES)
    ]
    if not valid_fu_values:
        raise ValueError("win_type 必须是 'ron' 或 'tsumo'")

    fu = rng.choices(
        valid_fu_values,
        weights=[NORMAL_FU_WEIGHTS[value] for value in valid_fu_values],
        k=1,
    )[0]
    valid_han_values = [
        han for han in NORMAL_HAN_VALUES
        if is_valid_normal_combo(win_type, fu, han)
    ]
    han = rng.choices(
        valid_han_values,
        weights=[
            NORMAL_COMBO_WEIGHT_OVERRIDES.get((fu, value), 1.0)
            for value in valid_han_values
        ],
        k=1,
    )[0]
    return fu, han


def _templates_for(win_type: str, family: str, fu: int, han: int) -> List[HandTemplate]:
    """找出能够通过 0～max_bonus 枚宝牌补到目标番数的模板。"""

    result = []
    for template in HAND_TEMPLATES:
        if template.win_type != win_type or template.family != family:
            continue
        if family == "normal" and template.fu != fu:
            continue
        needed = han - template.base_han
        if 0 <= needed <= template.max_bonus:
            result.append(template)
    return result


def create_question(rng: Optional[random.Random] = None) -> Question:
    """生成一道完整随机题。传入 Random 实例可让测试结果可重复。"""

    if rng is None:
        rng = random.Random()

    bucket = choose_question_bucket(rng)
    is_dealer = bool(rng.getrandbits(1))
    win_type = rng.choice(("ron", "tsumo"))

    if bucket == "normal":
        fu, han = choose_normal_combo(win_type, rng)
        candidates = _templates_for(win_type, "normal", fu, han)
        tier = "普通手"
    else:
        han = rng.choice(BUCKET_HAN[bucket])
        candidates = _templates_for(win_type, "high", 0, han)
        tier = limit_name(han)
        # 高番题的符数由实际牌型决定，不参与限制点计算。
        fu = 0

    if not candidates:
        raise RuntimeError("找不到 {} {} 番的牌型模板".format(win_type, han))

    template = rng.choice(candidates)
    fu = template.fu
    needed_bonus = han - template.base_han
    bonus = choose_bonus_plan(template, needed_bonus)
    expected = calculate_score(is_dealer, win_type, fu, han)
    return Question(is_dealer, win_type, fu, han, tier, template, bonus, expected)


# ---------------------------------------------------------------------------
# 四、输入解析、格式化与自检
# ---------------------------------------------------------------------------

TILE_NAMES: Dict[str, str] = {
    "E": "东", "S": "南", "W": "西", "N": "北",
    "P": "白", "F": "发", "C": "中",
}

# 牌图路径始终以脚本所在目录为基准，因此从任意工作目录启动都能找到素材。
ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets" / "tiles"
ASSET_SOURCE_SIZE = (600, 800)
ASSET_SUBSAMPLE = 10

# 内部牌编码与素材文件名的唯一映射。字牌文件名沿用素材项目的日文读音。
TILE_ASSET_FILES: Dict[str, str] = {
    **{"{}m".format(rank): "Man{}.png".format(rank) for rank in range(1, 10)},
    **{"{}p".format(rank): "Pin{}.png".format(rank) for rank in range(1, 10)},
    **{"{}s".format(rank): "Sou{}.png".format(rank) for rank in range(1, 10)},
    "E": "Ton.png",
    "S": "Nan.png",
    "W": "Shaa.png",
    "N": "Pei.png",
    "P": "Haku.png",
    "F": "Hatsu.png",
    "C": "Chun.png",
}
RED_FIVE_ASSET_FILES: Dict[str, str] = {
    "5m": "Man5-Dora.png",
    "5p": "Pin5-Dora.png",
    "5s": "Sou5-Dora.png",
}
REQUIRED_ASSET_FILES: Tuple[str, ...] = tuple(
    dict.fromkeys(
        ("Front.png", "Back.png")
        + tuple(TILE_ASSET_FILES.values())
        + tuple(RED_FIVE_ASSET_FILES.values())
    )
)


class AssetLoadError(RuntimeError):
    """牌图缺失、损坏或规格不一致时抛出的可读错误。"""


def read_png_size(path: Path) -> Tuple[int, int]:
    """仅用标准库读取 PNG 的 IHDR 宽高，不需要解码整张图片。"""

    try:
        with path.open("rb") as image_file:
            header = image_file.read(24)
    except OSError as exc:
        raise AssetLoadError("无法读取牌图 {}：{}".format(path, exc)) from exc

    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise AssetLoadError("牌图不是有效 PNG：{}".format(path))
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def validate_asset_files() -> None:
    """确认运行所需牌图全部存在，而且保持统一的 600×800 规格。"""

    missing = [
        filename for filename in REQUIRED_ASSET_FILES
        if not (ASSET_DIRECTORY / filename).is_file()
    ]
    if missing:
        raise AssetLoadError(
            "缺少牌图素材：{}。请保留完整的 assets/tiles 目录。".format(
                "、".join(missing)
            )
        )

    for filename in REQUIRED_ASSET_FILES:
        path = ASSET_DIRECTORY / filename
        actual_size = read_png_size(path)
        if actual_size != ASSET_SOURCE_SIZE:
            raise AssetLoadError(
                "牌图 {} 的尺寸是 {}×{}，要求统一为 {}×{}。".format(
                    filename, actual_size[0], actual_size[1],
                    ASSET_SOURCE_SIZE[0], ASSET_SOURCE_SIZE[1]
                )
            )


def split_display_groups(
    template: HandTemplate,
) -> Tuple[Tuple[Tuple[int, TileGroup], ...], Tuple[Tuple[int, TileGroup], ...]]:
    """把暗手牌和鸣牌分开；保留原索引，以便正确标记和牌张。"""

    concealed = tuple(
        (index, item) for index, item in enumerate(template.groups)
        if not item.is_open
    )
    called = tuple(
        (index, item) for index, item in enumerate(template.groups)
        if item.is_open
    )
    return concealed, called


class TileImageStore:
    """一次加载并缓存所有 Tk 牌图，避免每次重绘都读取磁盘。"""

    def __init__(self) -> None:
        if tk is None:
            raise AssetLoadError("当前 Python 缺少 tkinter/Tk，无法加载牌图。")
        validate_asset_files()
        self._images: Dict[str, object] = {}

        for filename in REQUIRED_ASSET_FILES:
            path = ASSET_DIRECTORY / filename
            try:
                source = tk.PhotoImage(file=str(path))
                image = source.subsample(ASSET_SUBSAMPLE, ASSET_SUBSAMPLE)
            except Exception as exc:
                raise AssetLoadError("Tk 无法加载牌图 {}：{}".format(path, exc)) from exc
            self._images[filename] = image

    @property
    def width(self) -> int:
        """界面中单张牌图的宽度。"""

        return ASSET_SOURCE_SIZE[0] // ASSET_SUBSAMPLE

    @property
    def height(self) -> int:
        """界面中单张牌图的高度。"""

        return ASSET_SOURCE_SIZE[1] // ASSET_SUBSAMPLE

    def front(self) -> object:
        """返回所有明牌共用的牌身底图。"""

        return self._images["Front.png"]

    def back(self) -> object:
        """返回牌背图。"""

        return self._images["Back.png"]

    def face(self, tile: str, aka: bool = False) -> object:
        """按内部编码返回普通牌面或赤五牌面。"""

        filename = (
            RED_FIVE_ASSET_FILES[tile]
            if aka else TILE_ASSET_FILES[tile]
        )
        return self._images[filename]


def tile_name(tile: str) -> str:
    """把内部牌编码转换为中文名称。"""

    if tile in TILE_NAMES:
        return TILE_NAMES[tile]
    suffix = {"m": "万", "p": "筒", "s": "索"}[tile[1]]
    return "{}{}".format(tile[0], suffix)


def parse_answer(raw: str, expected_parts: int) -> Optional[Tuple[int, ...]]:
    """
    解析用户答案。

    NFKC 规范化会把全角数字和全角斜杠转换为半角形式；逗号和空格
    会被忽略。格式不正确时返回 None，而不是让程序崩溃。
    """

    text = unicodedata.normalize("NFKC", raw).strip()
    text = text.replace(",", "").replace(" ", "")
    if expected_parts == 1:
        if text.isdigit():
            return (int(text),)
        return None
    if expected_parts == 2:
        pieces = text.split("/")
        if len(pieces) == 2 and all(piece.isdigit() for piece in pieces):
            return (int(pieces[0]), int(pieces[1]))
    return None


def format_expected(question: Question) -> str:
    """把正确答案格式化成适合界面显示的文字。"""

    if len(question.expected) == 1:
        if question.win_type == "tsumo":
            return "{} 点（每名子家支付）".format(question.expected[0])
        return "{} 点".format(question.expected[0])
    return "{}/{}（闲家/亲家）".format(*question.expected)


def format_yaku(question: Question) -> str:
    """生成答题后显示的役种与宝牌说明。"""

    items = ["{} {}番".format(name, value) for name, value in question.template.yaku]
    if question.bonus.visible_dora_count:
        items.append("宝牌 {}番".format(question.bonus.visible_dora_count))
    if question.bonus.aka_tile:
        items.append("赤宝牌 1番")
    return "、".join(items)


def format_fu_details(template: HandTemplate) -> str:
    """生成人工可读的符数明细。"""

    parts = ["{} {}符".format(name, value) for name, value in template.fu_items]
    raw_total = sum(value for _, value in template.fu_items)
    if template.fixed_fu:
        return "{}，固定 {}符".format(" + ".join(parts), template.fu)
    return "{} = {}符，进位为 {}符".format(" + ".join(parts), raw_total, template.fu)


def validate_template(template: HandTemplate) -> None:
    """验证模板的牌数、结构、符番和宝牌可达性。"""

    tiles = hand_tiles(template)
    if any(tile not in ALL_TILES for tile in tiles):
        raise AssertionError("{} 含未知牌编码".format(template.key))
    if any(count > 4 for count in Counter(tiles).values()):
        raise AssertionError("{} 有同种牌超过 4 张".format(template.key))

    # 七对子有 7 个对子；普通和牌必须是 4 个面子加 1 个对子。
    if len(template.groups) == 7:
        if any(item.kind != "pair" or len(item.tiles) != 2 for item in template.groups):
            raise AssertionError("{} 的七对子结构错误".format(template.key))
        if len(tiles) != 14:
            raise AssertionError("{} 的七对子牌数错误".format(template.key))
    else:
        if len(template.groups) != 5:
            raise AssertionError("{} 不是 4 面子 1 雀头".format(template.key))
        pair_count = sum(item.kind == "pair" for item in template.groups)
        meld_count = sum(item.kind in ("sequence", "triplet", "kan") for item in template.groups)
        if pair_count != 1 or meld_count != 4:
            raise AssertionError("{} 的面子数量错误".format(template.key))
        for item in template.groups:
            expected_length = 4 if item.kind == "kan" else (2 if item.kind == "pair" else 3)
            if len(item.tiles) != expected_length:
                raise AssertionError("{} 的 {} 长度错误".format(template.key, item.kind))
        kan_count = sum(item.kind == "kan" for item in template.groups)
        if len(tiles) != 14 + kan_count:
            raise AssertionError("{} 的实际牌数未计入杠牌".format(template.key))

    if not (0 <= template.win_group < len(template.groups)):
        raise AssertionError("{} 的和牌组索引错误".format(template.key))
    if not (0 <= template.win_index < len(template.groups[template.win_group].tiles)):
        raise AssertionError("{} 的和牌张索引错误".format(template.key))

    if sum(value for _, value in template.yaku) != template.base_han:
        raise AssertionError("{} 的基础番数与役种不一致".format(template.key))

    raw_fu = sum(value for _, value in template.fu_items)
    calculated_fu = raw_fu if template.fixed_fu else round_up_10(raw_fu)
    if calculated_fu != template.fu:
        raise AssertionError("{} 的符数明细不一致".format(template.key))

    if template.aka_tile is not None:
        if template.aka_tile not in ("5m", "5p", "5s") or template.aka_tile not in tiles:
            raise AssertionError("{} 的赤宝牌设置错误".format(template.key))

    # 确保从基础番到 max_bonus 的每一种补番都能找到真实指示牌。
    for needed in range(template.max_bonus + 1):
        plan = choose_bonus_plan(template, needed)
        if dora_from_indicator(plan.indicator) != plan.dora_tile:
            raise AssertionError("{} 的宝牌循环错误".format(template.key))
        if Counter(tiles)[plan.dora_tile] != plan.visible_dora_count:
            raise AssertionError("{} 的宝牌数量错误".format(template.key))
        if plan.total_bonus_han != needed:
            raise AssertionError("{} 未准确补足番数".format(template.key))


def run_self_checks(include_frequency_test: bool = False) -> None:
    """运行无需图形界面的内置自检。失败时会抛出 AssertionError。"""

    # 素材检查不创建 Tk 窗口，因此也能在 CI 和无桌面的服务器上执行。
    validate_asset_files()
    assert len(REQUIRED_ASSET_FILES) == 39

    # 低番荣和关键值，特别检查不能从已进位子家点数乘 1.5 的三格。
    assert CHILD_RON_TABLE[30][3] == 3900
    assert DEALER_RON_TABLE[30][3] == 5800
    assert DEALER_RON_TABLE[40][3] == 7700
    assert DEALER_RON_TABLE[70][1] == 3400
    assert DEALER_RON_TABLE[40][4] == 12000

    # 普通自摸与限制点自摸。
    assert calculate_tsumo(False, 30, 2) == (500, 1000)
    assert calculate_tsumo(True, 30, 2) == (1000,)
    assert calculate_limit_score(False, "ron", 5) == (8000,)
    assert calculate_limit_score(True, "ron", 7) == (18000,)
    assert calculate_limit_score(False, "tsumo", 10) == (4000, 8000)
    assert calculate_limit_score(True, "tsumo", 12) == (12000,)
    assert calculate_limit_score(False, "ron", 13) == (32000,)
    assert calculate_limit_score(True, "ron", 13) == (48000,)

    for template in HAND_TEMPLATES:
        validate_template(template)
        concealed_groups, called_groups = split_display_groups(template)
        # 展示顺序必须是全部暗牌在左、全部鸣牌在右，同时保留所有原始组。
        display_indices = tuple(index for index, _ in concealed_groups + called_groups)
        assert set(display_indices) == set(range(len(template.groups)))
        assert all(not item.is_open for _, item in concealed_groups)
        assert all(item.is_open for _, item in called_groups)

    # 所有有效普通组合都必须有模板。
    for win_type in ("ron", "tsumo"):
        for fu in FU_VALUES:
            for han in NORMAL_HAN_VALUES:
                candidates = _templates_for(win_type, "normal", fu, han)
                if is_valid_normal_combo(win_type, fu, han):
                    assert candidates, (win_type, fu, han)
                else:
                    assert not candidates, ("无效组合却有模板", win_type, fu, han)

    # 每个高番和两种和牌方式都必须能找到严格匹配的模板。
    for win_type in ("ron", "tsumo"):
        for han in range(5, 14):
            candidates = _templates_for(win_type, "high", 0, han)
            assert candidates, ("缺少高番模板", win_type, han)
            for candidate in candidates:
                choose_bonus_plan(candidate, han - candidate.base_han)

    # 统计测试只在 --self-test 下执行，避免每次打开窗口都做大量随机抽样。
    if include_frequency_test:
        rng = random.Random(20260903)
        sample_size = 100000
        counts = Counter(choose_question_bucket(rng) for _ in range(sample_size))
        expected_rates = dict(zip(QUESTION_BUCKETS, QUESTION_WEIGHTS))
        for bucket, expected_percent in expected_rates.items():
            actual_percent = counts[bucket] * 100.0 / sample_size
            assert abs(actual_percent - expected_percent) < 0.8, (
                bucket, actual_percent, expected_percent
            )

        # 普通题符数权重也用固定种子抽样。无效符数会被排除，其余权重按比例归一化。
        assert set(NORMAL_FU_WEIGHTS) == set(FU_VALUES)
        assert all(weight > 0 for weight in NORMAL_FU_WEIGHTS.values())
        assert sum(NORMAL_FU_WEIGHTS.values()) == 100.0
        for win_type in ("ron", "tsumo"):
            combo_rng = random.Random("20260903-{}".format(win_type))
            combo_counts = Counter(
                choose_normal_combo(win_type, combo_rng) for _ in range(sample_size)
            )
            valid_fu_values = [
                fu for fu in FU_VALUES
                if any(
                    is_valid_normal_combo(win_type, fu, han)
                    for han in NORMAL_HAN_VALUES
                )
            ]
            total_weight = sum(NORMAL_FU_WEIGHTS[fu] for fu in valid_fu_values)
            for fu in valid_fu_values:
                actual_percent = sum(
                    count for (sampled_fu, _), count in combo_counts.items()
                    if sampled_fu == fu
                ) * 100.0 / sample_size
                expected_percent = NORMAL_FU_WEIGHTS[fu] * 100.0 / total_weight
                assert abs(actual_percent - expected_percent) < 0.8, (
                    win_type, fu, actual_percent, expected_percent
                )

            # 1 番 70 符保留覆盖，但应明显少于同为 70 符的普通番数组合。
            assert 0 < combo_counts[(70, 1)] < combo_counts[(70, 2)] * 0.4


# ---------------------------------------------------------------------------
# 五、Tkinter 图形界面
# ---------------------------------------------------------------------------


class MahjongTrainerApp:
    """训练器主窗口。为了兼容缺少 Tk 的环境，不直接继承 Tk 类。"""

    TABLE_GREEN = "#0b5d3b"
    PANEL_BG = "#f4f1e8"
    TEXT_DARK = "#17221c"
    ACCENT = "#c73b32"

    def __init__(self, root: object) -> None:
        self.root = root
        self.rng = random.Random()
        self.question: Optional[Question] = None
        self.started_at = 0.0
        self.answered = False
        self.timer_generation = 0

        self.total_answers = 0
        self.correct_answers = 0
        self.fast_correct_answers = 0

        # PhotoImage 必须在 Tk 根窗口创建之后加载，并要由长生命周期对象持有引用。
        self.tile_images = TileImageStore()
        self._build_window()
        self.next_question()

    def _build_window(self) -> None:
        """创建固定布局；牌面本身在 Canvas 中按题目重绘。"""

        self.root.title("日麻点数计算训练器")
        self.root.geometry("1120x760")
        self.root.minsize(1020, 700)
        self.root.configure(bg=self.PANEL_BG)

        header = tk.Frame(self.root, bg="#18392c", padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(
            header, text="日麻点数计算训练器", bg="#18392c", fg="white",
            font=("Microsoft YaHei", 20, "bold")
        ).pack(side="left")
        tk.Label(
            header, text="雀魂四人麻将 · 1～13番", bg="#18392c", fg="#cfe5d7",
            font=("Microsoft YaHei", 11)
        ).pack(side="left", padx=(16, 0), pady=(7, 0))
        tk.Button(
            header, text="退出", command=self.root.destroy,
            bg="#2c5947", fg="white", activebackground="#376c57",
            activeforeground="white", relief="flat", padx=18, pady=10
        ).pack(side="right")

        info = tk.Frame(self.root, bg=self.PANEL_BG, padx=24, pady=12)
        info.pack(fill="x")
        self.question_var = tk.StringVar()
        self.timer_var = tk.StringVar()
        tk.Label(
            info, textvariable=self.question_var, bg=self.PANEL_BG, fg=self.TEXT_DARK,
            font=("Microsoft YaHei", 15, "bold"), anchor="w"
        ).pack(side="left", fill="x", expand=True)
        self.timer_label = tk.Label(
            info, textvariable=self.timer_var, bg=self.PANEL_BG, fg="#176b48",
            font=("Consolas", 14, "bold"), width=22, anchor="e"
        )
        self.timer_label.pack(side="right")

        self.canvas = tk.Canvas(
            self.root, height=300, bg=self.TABLE_GREEN,
            highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="x", padx=24)
        self.canvas.bind("<Configure>", lambda _event: self.draw_question())

        answer_panel = tk.Frame(self.root, bg=self.PANEL_BG, padx=24, pady=14)
        answer_panel.pack(fill="x")
        self.prompt_var = tk.StringVar()
        tk.Label(
            answer_panel, textvariable=self.prompt_var, bg=self.PANEL_BG,
            fg=self.TEXT_DARK, font=("Microsoft YaHei", 11)
        ).pack(anchor="w")

        input_row = tk.Frame(answer_panel, bg=self.PANEL_BG)
        input_row.pack(fill="x", pady=(8, 0))
        self.answer_entry = tk.Entry(
            input_row, font=("Consolas", 18), relief="solid", bd=1,
            bg="white", fg=self.TEXT_DARK, insertbackground=self.TEXT_DARK
        )
        self.answer_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.submit_button = tk.Button(
            input_row, text="提交答案", command=self.submit_answer,
            bg="#176b48", fg="white", activebackground="#0f5135",
            activeforeground="white", relief="flat", padx=24,
            font=("Microsoft YaHei", 11, "bold")
        )
        self.submit_button.pack(side="left", padx=(10, 0), ipady=9)
        self.next_button = tk.Button(
            input_row, text="下一题", command=self.next_question,
            bg="#345b73", fg="white", activebackground="#29495c",
            activeforeground="white", relief="flat", padx=24,
            font=("Microsoft YaHei", 11, "bold"), state="disabled"
        )
        self.next_button.pack(side="left", padx=(8, 0), ipady=9)

        self.result_var = tk.StringVar()
        self.result_label = tk.Label(
            answer_panel, textvariable=self.result_var, bg=self.PANEL_BG,
            fg=self.TEXT_DARK, font=("Microsoft YaHei", 12, "bold"),
            anchor="w", justify="left", wraplength=1040
        )
        self.result_label.pack(fill="x", pady=(10, 0))

        self.detail_var = tk.StringVar()
        tk.Label(
            answer_panel, textvariable=self.detail_var, bg="#e8e3d8",
            fg="#34443b", font=("Microsoft YaHei", 10), anchor="w",
            justify="left", wraplength=1020, padx=12, pady=9
        ).pack(fill="x", pady=(8, 0))

        footer = tk.Frame(self.root, bg="#e1dccf", padx=24, pady=10)
        footer.pack(side="bottom", fill="x")
        self.stats_var = tk.StringVar()
        tk.Label(
            footer, textvariable=self.stats_var, bg="#e1dccf", fg=self.TEXT_DARK,
            font=("Microsoft YaHei", 10, "bold"), anchor="w"
        ).pack(side="left")
        tk.Label(
            footer, text="Enter：提交/下一题　　超时后仍可作答",
            bg="#e1dccf", fg="#607066", font=("Microsoft YaHei", 9)
        ).pack(side="right")

        self.root.bind("<Return>", self._handle_enter)

    def next_question(self) -> None:
        """生成并展示下一题，同时重新开始 5 秒计时。"""

        self.question = create_question(self.rng)
        self.answered = False
        self.started_at = time.perf_counter()
        self.timer_generation += 1
        current_generation = self.timer_generation

        role = "亲家" if self.question.is_dealer else "子家"
        win_text = "荣和" if self.question.win_type == "ron" else "自摸"
        suffix = ""
        if self.question.han >= 5:
            suffix = " ｜ {}（符数不影响限制点）".format(self.question.tier)
        self.question_var.set(
            "第 {} 题 ｜ {} ｜ {} ｜ {}符 {}番{}".format(
                self.total_answers + 1, role, win_text,
                self.question.fu, self.question.han, suffix
            )
        )

        if self.question.win_type == "tsumo" and not self.question.is_dealer:
            self.prompt_var.set("请输入：闲家支付/亲家支付，例如 500/1000")
        elif self.question.win_type == "tsumo":
            self.prompt_var.set("请输入：每名子家应支付的点数")
        else:
            self.prompt_var.set("请输入：放铳者应支付的点数")

        self.answer_entry.configure(state="normal")
        self.answer_entry.delete(0, "end")
        self.answer_entry.focus_set()
        self.submit_button.configure(state="normal")
        self.next_button.configure(state="disabled")
        self.result_var.set("")
        self.detail_var.set("提交答案后显示役种、宝牌与符数明细。")
        self.result_label.configure(fg=self.TEXT_DARK)
        self._update_stats_label()
        self.draw_question()
        self._tick_timer(current_generation)

    def _tick_timer(self, generation: int) -> None:
        """每 0.1 秒刷新一次计时标签，不会在 5 秒时强制收走答案。"""

        if generation != self.timer_generation or self.answered:
            return
        elapsed = time.perf_counter() - self.started_at
        remaining = 5.0 - elapsed
        if remaining > 0:
            self.timer_var.set("剩余 {:.1f} 秒".format(remaining))
            self.timer_label.configure(fg="#176b48")
        else:
            self.timer_var.set("已超时，仍可作答")
            self.timer_label.configure(fg=self.ACCENT)
        self.root.after(100, lambda: self._tick_timer(generation))

    def submit_answer(self) -> None:
        """解析答案、更新两种正确率，并展示牌型解析。"""

        if self.answered or self.question is None:
            return

        raw = self.answer_entry.get().strip()
        if unicodedata.normalize("NFKC", raw).lower() in ("q", "quit", "退出"):
            self.root.destroy()
            return

        elapsed = time.perf_counter() - self.started_at
        parsed = parse_answer(raw, len(self.question.expected))
        is_correct = parsed == self.question.expected
        is_fast = elapsed <= 5.0

        self.total_answers += 1
        if is_correct:
            self.correct_answers += 1
        if is_correct and is_fast:
            self.fast_correct_answers += 1

        if is_correct and is_fast:
            headline = "✓ 答案正确，并在 5 秒内完成"
            color = "#176b48"
        elif is_correct:
            headline = "✓ 答案正确，但用时超过 5 秒"
            color = "#9a5a00"
        elif parsed is None:
            headline = "✗ 输入格式不正确"
            color = self.ACCENT
        elif is_fast:
            headline = "✗ 答案错误"
            color = self.ACCENT
        else:
            headline = "✗ 答案错误，且用时超过 5 秒"
            color = self.ACCENT

        self.result_var.set(
            "{} ｜ 正确答案：{} ｜ 用时 {:.2f} 秒".format(
                headline, format_expected(self.question), elapsed
            )
        )
        self.result_label.configure(fg=color)

        dora_text = "指示牌 {} → 宝牌 {}（手中 {} 枚）".format(
            tile_name(self.question.bonus.indicator),
            tile_name(self.question.bonus.dora_tile),
            self.question.bonus.visible_dora_count,
        )
        if self.question.bonus.aka_tile:
            dora_text += "，另有赤{} 1 枚".format(tile_name(self.question.bonus.aka_tile))

        limit_note = ""
        if self.question.han >= 5:
            limit_note = "\n档位：{}，实际 {}符不影响限制点。".format(
                self.question.tier, self.question.fu
            )
        self.detail_var.set(
            "役种：{}\n宝牌：{}\n符数：{}{}".format(
                format_yaku(self.question), dora_text,
                format_fu_details(self.question.template), limit_note
            )
        )

        self.answered = True
        self.timer_generation += 1
        self.timer_var.set("完成：{:.2f} 秒".format(elapsed))
        self.answer_entry.configure(state="disabled")
        self.submit_button.configure(state="disabled")
        self.next_button.configure(state="normal")
        self.next_button.focus_set()
        self._update_stats_label()

        if self.total_answers % 10 == 0:
            correct_rate = self.correct_answers * 100.0 / self.total_answers
            fast_rate = self.fast_correct_answers * 100.0 / self.total_answers
            messagebox.showinfo(
                "每 10 题统计",
                "已完成 {} 题\n\n答案正确：{} 题（{:.1f}%）\n"
                "5 秒内答对：{} 题（{:.1f}%）".format(
                    self.total_answers, self.correct_answers, correct_rate,
                    self.fast_correct_answers, fast_rate
                )
            )

    def _handle_enter(self, _event: object) -> str:
        """Enter 在答题前提交，在答题后进入下一题。"""

        if self.answered:
            self.next_question()
        else:
            self.submit_answer()
        return "break"

    def _update_stats_label(self) -> None:
        """刷新窗口底部的累计统计。"""

        if self.total_answers == 0:
            self.stats_var.set("已完成 0 题 ｜ 答案正确率 -- ｜ 5秒内答对率 --")
            return
        correct_rate = self.correct_answers * 100.0 / self.total_answers
        fast_rate = self.fast_correct_answers * 100.0 / self.total_answers
        self.stats_var.set(
            "已完成 {} 题 ｜ 答案正确率 {:.1f}% ｜ 5秒内答对率 {:.1f}%".format(
                self.total_answers, correct_rate, fast_rate
            )
        )

    # --------------------------- Canvas 绘牌 ---------------------------

    def draw_question(self) -> None:
        """根据当前题目重绘完整手牌、和牌张和宝牌指示牌。"""

        if self.question is None or not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")

        tile_w, tile_h = self.tile_images.width, self.tile_images.height
        tile_gap = 1
        called_gap = 30
        called_group_gap = 10
        concealed_groups, called_groups = split_display_groups(self.question.template)

        concealed_count = sum(len(item.tiles) for _, item in concealed_groups)
        concealed_width = concealed_count * (tile_w + tile_gap) - tile_gap
        called_width = sum(
            len(item.tiles) * (tile_w + tile_gap) - tile_gap
            for _, item in called_groups
        )
        if called_groups:
            called_width += called_group_gap * (len(called_groups) - 1)
        total_width = concealed_width
        if called_groups:
            total_width += called_gap + called_width

        canvas_width = max(self.canvas.winfo_width(), 972)
        x = max(18, (canvas_width - total_width) / 2)
        y = 34
        aka_drawn = False

        self.canvas.create_text(
            18, 13, anchor="w", fill="#d8efe2",
            text="和牌牌型（描边与“和”标记为和牌张）",
            font=("Microsoft YaHei", 10, "bold")
        )

        # 暗牌区完全连续排列，不通过空隙泄露面子和雀头的拆分方式。
        for group_index, tile_group in concealed_groups:
            for tile_index, tile in enumerate(tile_group.tiles):
                face_down = (
                    tile_group.kind == "kan"
                    and tile_index in (0, len(tile_group.tiles) - 1)
                )
                is_winner = (
                    group_index == self.question.template.win_group
                    and tile_index == self.question.template.win_index
                )
                is_aka = False
                if (
                    not aka_drawn and not face_down
                    and self.question.bonus.aka_tile == tile
                ):
                    is_aka = True
                    aka_drawn = True
                self._draw_tile(x, y, tile, tile_w, tile_h, face_down, is_winner, is_aka)
                x += tile_w + tile_gap

        # 鸣牌与暗牌之间仅保留一个清晰分区间隔，所有鸣牌都排在最右侧。
        if called_groups:
            x += called_gap - tile_gap
            called_start = x
            for called_index, (group_index, tile_group) in enumerate(called_groups):
                if called_index:
                    x += called_group_gap - tile_gap
                for tile_index, tile in enumerate(tile_group.tiles):
                    is_winner = (
                        group_index == self.question.template.win_group
                        and tile_index == self.question.template.win_index
                    )
                    is_aka = False
                    if not aka_drawn and self.question.bonus.aka_tile == tile:
                        is_aka = True
                        aka_drawn = True
                    self._draw_tile(
                        x, y, tile, tile_w, tile_h,
                        False, is_winner, is_aka
                    )
                    x += tile_w + tile_gap

            called_end = x - tile_gap
            self.canvas.create_text(
                (called_start + called_end) / 2,
                y + tile_h + 27,
                text="鸣牌",
                fill="#d8efe2",
                font=("Microsoft YaHei", 9, "bold")
            )

        # 宝牌指示牌单独放在下方，确保用户看到的宝牌数量可自行复核。
        dora_x = 30
        dora_y = 188
        self.canvas.create_text(
            dora_x, dora_y - 17, anchor="w", fill="#d8efe2",
            text="宝牌指示牌", font=("Microsoft YaHei", 9, "bold")
        )
        self._draw_tile(
            dora_x, dora_y, self.question.bonus.indicator,
            tile_w, tile_h, False, False, False
        )
        self.canvas.create_text(
            dora_x + tile_w + 14, dora_y + tile_h / 2,
            anchor="w", fill="#d8efe2", font=("Microsoft YaHei", 10),
            text="→ 宝牌 {}".format(tile_name(self.question.bonus.dora_tile))
        )

        if self.question.bonus.aka_tile:
            self.canvas.create_text(
                dora_x + 190, dora_y + tile_h / 2,
                anchor="w", fill="#ffd6ce", font=("Microsoft YaHei", 10, "bold"),
                text="含赤{} 1枚".format(tile_name(self.question.bonus.aka_tile))
            )

        self.canvas.create_text(
            canvas_width - 24, dora_y + tile_h / 2,
            anchor="e", fill="#c8e1d1", font=("Microsoft YaHei", 9),
            text="牌面、和牌方式、符数与番数均与题目一致"
        )

    def _draw_tile(
        self,
        x: float,
        y: float,
        tile: str,
        width: int,
        height: int,
        face_down: bool,
        winner: bool,
        aka: bool,
    ) -> None:
        """用缓存的统一规格 PNG 绘制牌身、牌面及非纯颜色的和牌标记。"""

        # 轻微阴影让相邻牌仍有边界，但不会形成面子之间的视觉分组。
        self.canvas.create_rectangle(
            x + 2, y + 3, x + width + 2, y + height + 3,
            fill="#073e29", outline=""
        )

        if face_down:
            self.canvas.create_image(
                x, y, anchor="nw", image=self.tile_images.back()
            )
        else:
            # 原素材把共用牌身和透明牌面分开导出，因此需要按顺序叠放两层。
            self.canvas.create_image(
                x, y, anchor="nw", image=self.tile_images.front()
            )
            self.canvas.create_image(
                x, y, anchor="nw", image=self.tile_images.face(tile, aka)
            )

        if aka:
            self.canvas.create_text(
                x + width - 4, y + 4, anchor="ne", text="赤",
                fill="#a91f1a", font=("Microsoft YaHei", 7, "bold")
            )
        if winner:
            self.canvas.create_rectangle(
                x - 2, y - 2, x + width + 2, y + height + 2,
                outline="#ff9a86", width=3
            )
            self.canvas.create_text(
                x + width / 2, y + height + 11, text="和",
                fill="#ffe0d9", font=("Microsoft YaHei", 9, "bold")
            )


# ---------------------------------------------------------------------------
# 六、程序入口
# ---------------------------------------------------------------------------


def print_help() -> None:
    """输出极简命令行帮助。"""

    print("日麻点数计算训练器")
    print("  直接运行：打开图形训练界面")
    print("  --self-test：运行点数、牌型、牌图和概率自检")


def main() -> int:
    """先自检核心数据，再启动 Tkinter 窗口。"""

    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()
        return 0

    if "--self-test" in sys.argv:
        try:
            run_self_checks(include_frequency_test=True)
        except AssetLoadError as exc:
            print("牌图素材检查失败：{}".format(exc))
            return 1
        print("全部自检通过：点数表、牌型模板、牌图、宝牌和随机权重均正常。")
        return 0

    # 正常启动时执行快速自检；统计抽样只在 --self-test 中运行。
    try:
        run_self_checks(include_frequency_test=False)
    except AssetLoadError as exc:
        print("牌图素材检查失败：{}".format(exc))
        return 1

    if tk is None:
        print("无法启动图形界面：当前 Python 缺少 tkinter/Tk 支持。")
        print("Windows/macOS 请重新安装包含 Tcl/Tk 的官方 Python。")
        print("部分 Linux 可安装系统提供的 python3-tk 包（不是 Python 第三方包）。")
        print("原始错误：{}".format(TK_IMPORT_ERROR))
        return 1

    try:
        root = tk.Tk()
    except Exception as exc:  # 例如无图形桌面或 DISPLAY 未设置
        print("无法创建图形窗口：{}".format(exc))
        print("请在带桌面环境的终端中运行本程序。")
        return 1

    try:
        MahjongTrainerApp(root)
    except AssetLoadError as exc:
        message = "牌图素材加载失败：{}".format(exc)
        print(message)
        if messagebox is not None:
            messagebox.showerror("无法加载牌图", message)
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
