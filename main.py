import asyncio
import random
import time
from functools import wraps
from typing import Optional, List

import flet as ft

BROWN = "#805E52"
GREEN = "#7AA874"
RED = "#982c33"
YELLOW = "#F6BA6F"
DIMENSION = 9


def ms_to_time(ms):
    # 毫秒转换为时间格式
    ms = int(ms)
    minute, second = divmod(ms / 1000, 60)
    minute = min(99, minute)
    return "%02d:%02d" % (minute, second)


def async_partial(f, *args):
    @wraps(f)
    async def f2(*args2):
        result = f(*args, *args2)
        if asyncio.iscoroutinefunction(f):
            result = await result
        return result

    return f2


class SudokuRectangle(ft.UserControl):
    def __init__(self, parent, x, y, v):
        self.parent = parent
        self.x = x
        self.y = y
        self.v = v
        self.v_text: Optional[ft.Text] = None
        self.ui: Optional[ft.Container] = None
        super().__init__()
        self.prev_color = None

    def build(self):
        self.v_text = ft.Text(self.v, size=16, text_align=ft.TextAlign.CENTER)
        self.ui = ft.Container(
            content=self.v_text,
            width=40,
            height=40,
            animate=300,
            padding=0,
            border=ft.border.all(color="black"),
            on_click=self.set_select,
            alignment=ft.alignment.center,
        )
        return self.ui

    async def set_select(self, e=None):
        if self.parent.selected:
            await self.parent.selected.unselect()
        self.parent.selected = self
        self.ui.border = ft.border.all(color=YELLOW)
        await self.update_async()

    async def unselect(self):
        if self.parent.selected == self:
            self.parent.selected = None
        self.ui.border = ft.border.all(color="black")
        await self.update_async()

    async def set_uncertain(self):
        self.v = ""
        self.v_text.value = ""
        self.ui.bgcolor = None
        self.disabled = False
        await self.update_async()

    async def set_default(self, v):
        self.v = v
        self.v_text.value = str(v)
        self.ui.bgcolor = BROWN
        self.disabled = True
        await self.update_async()


class SudokuGrid(ft.UserControl):
    def __init__(self, parent: "_Sudoku"):
        self.parent = parent
        self.selected: Optional[SudokuRectangle] = None
        self.board = [[]]
        super().__init__()
        self.rows: Optional[List[ft.Row]] = None
        self.grid: Optional[ft.Column] = None
        self.start_time = 0

    def build(self):
        self.grid = ft.Column(opacity=1, animate_opacity=300)
        self.rows = [
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[SudokuRectangle(self, i, j, "") for j in range(9)],
            )
            for i in range(9)
        ]
        self.grid.controls = self.rows
        return self.grid

    async def input(self, v):
        if not self.selected:
            return
        incorrents = 0
        # update curr position
        self.selected.v = str(v)
        self.selected.v_text.value = str(v)
        i, j = self.selected.x, self.selected.y
        if self.is_valid_move(self.board, i, j, int(v)):
            self.selected.ui.bgcolor = GREEN
        else:
            incorrents += 1
            self.selected.ui.bgcolor = RED
        self.board[i][j] = v
        await self.selected.update_async()
        # update all positions
        not_filled = 0
        for i in range(DIMENSION):
            row = self.rows[i]
            for j in range(DIMENSION):
                rectangle = row.controls[j]
                if not rectangle.disabled:
                    if not rectangle.v_text.value:
                        not_filled += 1
                    else:
                        self.board[i][j], tmp = "", self.board[i][j]
                        if self.is_valid_move(
                            self.board, i, j, int(rectangle.v_text.value)
                        ):
                            rectangle.ui.bgcolor = GREEN
                        else:
                            incorrents += 1
                            rectangle.ui.bgcolor = RED
                        self.board[i][j] = tmp
                        await rectangle.update_async()
        # check if succeed
        if incorrents == 0:
            if not_filled == 0:
                self.parent.result_text.value = (
                    f"SUCCEED! COST {ms_to_time(time.time() * 1000 - self.start_time)}"
                )
                await self.parent.update_async()

    async def generate(self, level):
        # 第一步：生成一个完整的数独游戏
        # 构造一个二维列表，初始化所有数字都为 0
        self.board = [[0] * DIMENSION for _ in range(DIMENSION)]
        # 随机选择第一行的数字
        first_row = list(range(1, DIMENSION + 1))
        random.shuffle(first_row)
        for j in range(DIMENSION):
            self.board[0][j] = first_row[j]
        # 填充数独游戏，保证每行、每列、每宫都只有唯一的数字
        self.solve_sudoku(self.board, 0, 0)
        if level == "EASY":
            blank_min, blank_max = 25, 30
        elif level == "MEDIUM":
            blank_min, blank_max = 30, 35
        else:
            blank_min, blank_max = 35, 45
        blanks = random.randint(blank_min, blank_max)  # 随机确定需要清空的格子数量
        count = 0
        while count < blanks:
            i, j = random.randint(0, DIMENSION - 1), random.randint(0, DIMENSION - 1)
            if self.board[i][j] == 0:  # 如果该格子已经被清空，则继续选择
                continue
            temp = self.board[i][j]
            self.board[i][j] = 0
            # 检查清空该格子后是否唯一可解，如果不唯一则恢复原状态
            if not self.is_valid_sudoku(self.board) or not self.has_unique_solution(
                self.board
            ):
                self.board[i][j] = temp
                continue
            count += 1
        for i in range(DIMENSION):
            row = self.rows[i]
            for j in range(DIMENSION):
                v = self.board[i][j]
                rectangle = row.controls[j]
                if v == 0:
                    await rectangle.set_uncertain()
                else:
                    await rectangle.set_default(v)
        self.start_time = time.time() * 1000
        return self.board

    # 判断数独是否有效（即每行、每列、每宫都只有唯一的数字）
    @staticmethod
    def is_valid_sudoku(board):
        row_set = [set() for _ in range(DIMENSION)]
        col_set = [set() for _ in range(DIMENSION)]
        box_set = [set() for _ in range(DIMENSION)]
        for i in range(DIMENSION):
            for j in range(DIMENSION):
                num = board[i][j]
                if num == 0:
                    continue
                if (
                    num in row_set[i]
                    or num in col_set[j]
                    or num in box_set[(i // 3) * 3 + j // 3]
                ):
                    return False
                row_set[i].add(num)
                col_set[j].add(num)
                box_set[(i // 3) * 3 + j // 3].add(num)
        return True

    # 判断数独是否有唯一解
    def has_unique_solution(self, board):
        return self.solve_sudoku(board, 0, 0, True, inplace=False) == 1

    # 解数独，使用回溯法进行求解
    def solve_sudoku(self, board, i, j, count_solutions=False, inplace=True):
        if not inplace:
            board = [i[:] for i in board]
        if j == DIMENSION:
            i, j = i + 1, 0
            if i == DIMENSION:
                return 1
        if board[i][j] != 0:
            return self.solve_sudoku(board, i, j + 1, count_solutions)
        for num in range(1, DIMENSION + 1):
            if self.is_valid_move(board, i, j, num):
                board[i][j] = num
                solutions_count = self.solve_sudoku(board, i, j + 1, count_solutions)
                if count_solutions and solutions_count > 1:
                    return solutions_count
                if solutions_count == 1:
                    return 1
                board[i][j] = 0
        return 0

    # 判断在 (i, j) 处填入 num 是否符合数独的规则
    @staticmethod
    def is_valid_move(board, i, j, num):
        for k in range(DIMENSION):
            if (
                board[i][k] == num
                or board[k][j] == num
                or board[(i // 3) * 3 + k // 3][(j // 3) * 3 + k % 3] == num
            ):
                return False
        return True


class _Sudoku(ft.UserControl):
    def __init__(self, title):
        self.title = title
        super().__init__()
        self.difficulty: Optional[ft.Dropdown] = None
        self.game_text: Optional[ft.Text] = None
        self.result_text: Optional[ft.Text] = None
        self.options_btn: Optional[ft.Row] = None
        self.start_button: Optional[ft.Container] = None
        self.grid: Optional[SudokuGrid] = None
        self.ui: Optional[ft.Column] = None

    def build(self):
        self.difficulty = ft.Dropdown(
            value="EASY",
            options=[
                ft.dropdown.Option("EASY"),
                ft.dropdown.Option("MEDIUM"),
                ft.dropdown.Option("HARD"),
            ],
            text_size=13,
            content_padding=ft.padding.only(10, 0, 0, 10),
            height=40,
            width=100,
        )
        self.game_text = ft.Text(self.title, size=22, weight=ft.FontWeight.BOLD)
        self.result_text = ft.Text(size=16, color=GREEN, weight=ft.FontWeight.BOLD)
        self.options_btn = ft.Row(
            [
                ft.OutlinedButton(
                    str(i),
                    style=ft.ButtonStyle(shape=ft.BeveledRectangleBorder()),
                    width=40,
                    height=40,
                    on_click=async_partial(self.input, i),
                )
                for i in range(1, DIMENSION + 1)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        self.options_btn.visible = False
        self.start_button = ft.Container(
            content=ft.ElevatedButton(
                on_click=self.start_game,
                content=ft.Text("开始!", size=13, weight=ft.FontWeight.BOLD),
                style=ft.ButtonStyle(
                    shape={"": ft.RoundedRectangleBorder(radius=8)},
                    color={"": "white"},
                    bgcolor=ft.colors.AMBER,
                ),
                height=45,
                width=255,
            )
        )
        self.grid = SudokuGrid(self)
        self.grid.visible = False
        self.ui = ft.Column(
            [
                self.game_text,
                self.result_text,
                ft.Divider(height=10, color="transparent"),
                self.grid,
                ft.Divider(height=10, color="transparent"),
                self.options_btn,
                ft.Divider(height=10, color="transparent"),
                self.difficulty,
                self.start_button,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return self.ui

    async def start_game(self, e=None):
        self.grid.visible = True
        await self.grid.generate(self.difficulty.value)
        self.grid.grid.opacity = 1
        await self.grid.update_async()
        self.result_text.value = ""
        self.options_btn.visible = True
        await self.update_async()

    async def input(self, v, e=None):
        await self.grid.input(v)


async def main(page: ft.Page):
    page.title = "Sudoku"
    page.window_width = 550
    page.window_height = 800
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    await page.window_center_async()

    await page.add_async(_Sudoku("SUDOKU"))
    await page.update_async()


if __name__ == "__main__":
    ft.app(target=main)
