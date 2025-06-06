# -*- coding: utf-8 -*-
import clr
import os
import json
import random

clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

import System
from System.Windows.Markup import XamlReader
from System.IO import FileStream, FileMode
from System.Windows import Window, Thickness
from System.Windows.Controls import Button, Canvas, StackPanel, TextBlock, ScrollViewer, RadioButton, ComboBox
from System.Windows.Shapes import Rectangle, Line
from System.Windows.Media import SolidColorBrush, Colors
from System.Windows.Threading import DispatcherTimer
from System import TimeSpan

cell_size = 20
cols = 20
rows = 20

script_dir = os.path.dirname(os.path.abspath(__file__))
save_file = os.path.join(script_dir, "snake_save.json")

skins = [
    {"name": u"Классика", "color": Colors.Green, "purchased": True, "price": 0},
    {"name": u"Синий", "color": Colors.Blue, "purchased": False, "price": 20},
    {"name": u"Жёлтый", "color": Colors.Yellow, "purchased": False, "price": 40},
    {"name": u"Фиолетовый", "color": Colors.Purple, "purchased": False, "price": 60},
]
current_skin_index = 0

def make_border():
    wall = []
    for i in range(cols):
        wall.append((i, 0))
        wall.append((i, rows-1))
    for j in range(rows):
        wall.append((0, j))
        wall.append((cols-1, j))
    return wall

def make_border_with_gaps(gap_width=4):
    wall = []
    gap_start = (cols // 2) - (gap_width // 2)
    gap_end = gap_start + gap_width
    # Верх и низ с окнами
    for i in range(cols):
        if not (gap_start <= i < gap_end):
            wall.append((i, 0))
            wall.append((i, rows-1))
    # Лево и право с окнами
    for j in range(rows):
        if not (gap_start <= j < gap_end):
            wall.append((0, j))
            wall.append((cols-1, j))
    return wall

border = make_border()
custom_perimeter = make_border_with_gaps(gap_width=4)

maps = [
    [],  # 0: Без препятствий
    border + [(i, 10) for i in range(5, 15)],   # 1: Горизонтальная стена
    border + [(10, i) for i in range(5, 15)],   # 2: Вертикальная стена
    border + [(i, i) for i in range(5, 15) if i != 10], # 3: Диагональ (без центра)
    border,                                     # 4: Просто рамка
    custom_perimeter,                           # 5: Рамка с окнами
]
selected_map_index = 0

# Для wrap через окна нужны координаты дырок
GAP_WIDTH = 4
gap_start = (cols // 2) - (GAP_WIDTH // 2)
gap_end = gap_start + GAP_WIDTH

def is_gap_on_edge(x, y):
    # Возвращает True, если координата (x, y) лежит на "дырке" в соответствующей границе
    if y < 0 and (gap_start <= x < gap_end):       # выход вверх через окно
        return True
    if y >= rows and (gap_start <= x < gap_end):   # вниз через окно
        return True
    if x < 0 and (gap_start <= y < gap_end):       # влево через окно
        return True
    if x >= cols and (gap_start <= y < gap_end):   # вправо через окно
        return True
    return False

def wrap_through_gap(x, y):
    # Возвращает wrap-координаты (только через окна)
    if y < 0:
        return (x, rows-1)
    if y >= rows:
        return (x, 0)
    if x < 0:
        return (cols-1, y)
    if x >= cols:
        return (0, y)
    return (x, y)

xaml_path = os.path.join(script_dir, "snake_ui.xaml")
stream = FileStream(xaml_path, FileMode.Open)
window = XamlReader.Load(stream)
stream.Close()

game_canvas = window.FindName("GameCanvas")
score_text = window.FindName("ScoreText")
exit_button = window.FindName("ExitButton")
pause_button = window.FindName("PauseButton")
shop_button = window.FindName("ShopButton")
start_button = window.FindName("StartButton")
map_combo = window.FindName("MapCombo")

snake = [(10, 10)]
direction = (0, -1)
food = (random.randint(0, cols-1), random.randint(0, rows-1))
score = 0
is_paused = False
game_running = False
shop_window = None
obstacles = []
wrap_mode = False
wrap_gaps_mode = False

def load_save():
    global current_skin_index, score
    try:
        with open(save_file, "r") as f:
            data = json.load(f)
            current_skin_index = data.get("current_skin_index", 0)
            score = data.get("score", 0)
            purchased = data.get("purchased_skins", {})
            for i, skin in enumerate(skins):
                skin["purchased"] = purchased.get(str(i), skin["purchased"])
    except:
        pass

def save_state():
    data = {
        "current_skin_index": current_skin_index,
        "score": score,
        "purchased_skins": {str(i): skin["purchased"] for i, skin in enumerate(skins)}
    }
    try:
        with open(save_file, "w") as f:
            json.dump(data, f)
    except:
        pass

def draw_grid():
    to_remove = []
    from System.Windows.Shapes import Line
    for child in game_canvas.Children:
        if isinstance(child, Line):
            to_remove.append(child)
    for child in to_remove:
        game_canvas.Children.Remove(child)
    for i in range(cols + 1):
        x = i * cell_size
        line = Line()
        line.Stroke = SolidColorBrush(Colors.LightGray)
        line.X1 = x
        line.Y1 = 0
        line.X2 = x
        line.Y2 = rows * cell_size
        line.StrokeThickness = 1
        game_canvas.Children.Add(line)
    for j in range(rows + 1):
        y = j * cell_size
        line = Line()
        line.Stroke = SolidColorBrush(Colors.LightGray)
        line.X1 = 0
        line.Y1 = y
        line.X2 = cols * cell_size
        line.Y2 = y
        line.StrokeThickness = 1
        game_canvas.Children.Add(line)

def draw_field():
    to_remove = []
    for child in game_canvas.Children:
        if isinstance(child, Rectangle):
            to_remove.append(child)
    for child in to_remove:
        game_canvas.Children.Remove(child)
    draw_grid()
    for x, y in obstacles:
        rect = Rectangle()
        rect.Width = cell_size - 2
        rect.Height = cell_size - 2
        rect.Fill = SolidColorBrush(Colors.Gray)
        game_canvas.Children.Add(rect)
        from System.Windows.Controls import Canvas as C
        C.SetLeft(rect, x * cell_size)
        C.SetTop(rect, y * cell_size)
    for x, y in snake:
        rect = Rectangle()
        rect.Width = cell_size - 2
        rect.Height = cell_size - 2
        rect.Fill = SolidColorBrush(skins[current_skin_index]["color"])
        game_canvas.Children.Add(rect)
        from System.Windows.Controls import Canvas as C
        C.SetLeft(rect, x * cell_size)
        C.SetTop(rect, y * cell_size)
    fx, fy = food
    rect = Rectangle()
    rect.Width = cell_size - 2
    rect.Height = cell_size - 2
    rect.Fill = SolidColorBrush(Colors.Red)
    game_canvas.Children.Add(rect)
    from System.Windows.Controls import Canvas as C
    C.SetLeft(rect, fx * cell_size)
    C.SetTop(rect, fy * cell_size)

def update_score():
    score_text.Text = u"Счёт: {}".format(score)

def find_start_pos(obstacles):
    cx, cy = cols // 2, rows // 2
    if (cx, cy) not in obstacles:
        return (cx, cy)
    for r in range(1, max(cols, rows)):
        for dx in range(-r, r+1):
            for dy in range(-r, r+1):
                x, y = cx+dx, cy+dy
                if 0 <= x < cols and 0 <= y < rows:
                    if (x, y) not in obstacles:
                        return (x, y)
    return (0, 0)

def start_game(sender, e):
    global game_running, snake, direction, food, score, is_paused, obstacles, selected_map_index, wrap_mode, wrap_gaps_mode
    game_running = True
    is_paused = False
    selected_map_index = map_combo.SelectedIndex
    obstacles = list(maps[selected_map_index])
    wrap_mode = (selected_map_index == 0)
    wrap_gaps_mode = (selected_map_index == 5)  # только для "рамка с окнами"
    start_pos = find_start_pos(obstacles)
    snake[:] = [start_pos]
    direction = (0, -1)
    while True:
        food_x, food_y = random.randint(0, cols-1), random.randint(0, rows-1)
        if (food_x, food_y) not in snake and (food_x, food_y) not in obstacles:
            break
    global food
    food = (food_x, food_y)
    score = 0
    update_score()
    draw_field()
    timer.Interval = TimeSpan.FromMilliseconds(150)
    timer.Start()
    start_button.Visibility = System.Windows.Visibility.Collapsed
    pause_button.IsEnabled = True
    shop_button.IsEnabled = True
    map_combo.IsEnabled = False

start_button.Click += start_game

def on_tick(sender, e):
    if not game_running or is_paused:
        return
    global snake, food, score, direction
    head = (snake[-1][0] + direction[0], snake[-1][1] + direction[1])
    new_head = head

    if wrap_mode:
        new_head = (head[0] % cols, head[1] % rows)
    elif wrap_gaps_mode:
        # Wrap только если "голова" выходит в отверстие
        if (
            (head[1] < 0 and gap_start <= head[0] < gap_end) or           # вверх через окно
            (head[1] >= rows and gap_start <= head[0] < gap_end) or       # вниз через окно
            (head[0] < 0 and gap_start <= head[1] < gap_end) or           # влево через окно
            (head[0] >= cols and gap_start <= head[1] < gap_end)          # вправо через окно
        ):
            # телепортируем в окно напротив
            if head[1] < 0:           # вверх
                new_head = (head[0], rows-1)
            elif head[1] >= rows:     # вниз
                new_head = (head[0], 0)
            elif head[0] < 0:         # влево
                new_head = (cols-1, head[1])
            elif head[0] >= cols:     # вправо
                new_head = (0, head[1])
        else:
            new_head = head

    # Проверяем столкновение (но не с wrap-дыркой)
    if (
        new_head in snake
        or (not wrap_mode and not wrap_gaps_mode and new_head in obstacles)
        or (wrap_gaps_mode and (
            # Если не wrap (остались вне поля, но не через окно) — проигрыш
            (new_head[0] < 0 or new_head[0] >= cols or new_head[1] < 0 or new_head[1] >= rows)
            or (0 <= new_head[0] < cols and 0 <= new_head[1] < rows and new_head in obstacles)
        ))
    ):
        on_game_over()
        return

    snake.append(new_head)
    if new_head == food:
        score += 1
        update_score()
        if score % 5 == 0 and timer.Interval > TimeSpan.FromMilliseconds(50):
            timer.Interval = TimeSpan.FromMilliseconds(max(50, timer.Interval.TotalMilliseconds - 15))
        while True:
            food_x, food_y = random.randint(0, cols-1), random.randint(0, rows-1)
            if (food_x, food_y) not in snake and (food_x, food_y) not in obstacles:
                break
        food = (food_x, food_y)
        save_state()
    else:
        snake.pop(0)
    draw_field()

def on_game_over():
    global game_running
    timer.Stop()
    game_running = False
    pause_button.IsEnabled = False
    shop_button.IsEnabled = False
    map_combo.IsEnabled = True

    restart_requested = [False]

    win = Window()
    win.Title = u"Игра окончена"
    win.Width = 250
    win.Height = 160
    win.WindowStartupLocation = System.Windows.WindowStartupLocation.CenterScreen
    win.ResizeMode = System.Windows.ResizeMode.NoResize
    grid = StackPanel()
    win.Content = grid
    tb = TextBlock()
    tb.Text = u"Вы проиграли!\nВаш счёт: {}".format(score)
    tb.Margin = Thickness(10)
    tb.FontSize = 16
    grid.Children.Add(tb)
    btn = Button()
    btn.Content = u"Повторить"
    btn.Margin = Thickness(10)
    btn.Width = 100
    btn.Height = 35
    def restart(sender, e):
        restart_requested[0] = True
        if win:
            win.Close()
    btn.Click += restart
    grid.Children.Add(btn)
    def on_closing(sender, e):
        if not restart_requested[0]:
            restart_requested[0] = True  # При нажатии крестика
    win.Closing += on_closing
    win.ShowDialog()
    save_state()
    if restart_requested[0]:
        start_button.Visibility = System.Windows.Visibility.Visible
        pause_button.IsEnabled = False
        shop_button.IsEnabled = False
        map_combo.IsEnabled = True

def on_key_down(sender, e):
    global direction
    if not game_running or is_paused:
        return
    key = e.Key.ToString()
    if key == "Left" and direction != (1, 0):
        direction = (-1, 0)
    elif key == "Right" and direction != (-1, 0):
        direction = (1, 0)
    elif key == "Up" and direction != (0, 1):
        direction = (0, -1)
    elif key == "Down" and direction != (0, -1):
        direction = (0, 1)
    draw_field()

def on_exit(sender, e):
    timer.Stop()
    save_state()
    window.Close()

exit_button.Click += on_exit

def on_pause(sender, e):
    global is_paused
    if not game_running:
        return
    if is_paused:
        is_paused = False
        pause_button.Content = u"Пауза"
        timer.Start()
    else:
        is_paused = True
        pause_button.Content = u"Продолжить"
        timer.Stop()

pause_button.Click += on_pause

def open_shop(sender, e):
    if not game_running:
        return
    global shop_window, is_paused
    is_paused = True
    timer.Stop()
    pause_button.Content = u"Продолжить"
    shop_window = Window()
    shop_window.Title = u"Магазин скинов"
    shop_window.Width = 320
    shop_window.Height = 450
    shop_window.WindowStartupLocation = System.Windows.WindowStartupLocation.CenterScreen
    shop_window.Background = SolidColorBrush(Colors.Black)
    shop_window.WindowStyle = System.Windows.WindowStyle.None
    shop_window.ResizeMode = System.Windows.ResizeMode.NoResize
    scroll = ScrollViewer()
    stack = StackPanel()
    scroll.Content = stack
    shop_window.Content = scroll

    def buy_skin(index):
        global score
        skin = skins[index]
        if not skin["purchased"]:
            price = skin["price"]
            if score >= price:
                score -= price
                skin["purchased"] = True
                update_score()
                save_state()
                build_shop_ui()
            else:
                System.Windows.MessageBox.Show(u"Недостаточно очков для покупки этого скина.")

    def select_skin(index):
        global current_skin_index
        current_skin_index = index
        save_state()
        draw_field()
        build_shop_ui()

    def build_shop_ui():
        stack.Children.Clear()
        for i, skin in enumerate(skins):
            sp = StackPanel()
            sp.Orientation = System.Windows.Controls.Orientation.Horizontal
            name_tb = TextBlock()
            name_tb.Text = skin["name"]
            name_tb.Width = 120
            name_tb.Foreground = SolidColorBrush(Colors.White)
            name_tb.FontSize = 14
            sp.Children.Add(name_tb)
            if skin["purchased"]:
                rb = RadioButton()
                rb.GroupName = "skins"
                rb.IsChecked = (current_skin_index == i)
                rb.Checked += lambda s, e, idx=i: select_skin(idx)
                sp.Children.Add(rb)
            else:
                btn = Button()
                btn.Content = u"Купить за {}".format(skin["price"])
                btn.IsEnabled = score >= skin["price"]
                btn.Click += lambda s, e, idx=i: buy_skin(idx)
                sp.Children.Add(btn)
            stack.Children.Add(sp)
        close_btn = Button()
        close_btn.Content = u"Закрыть"
        close_btn.Height = 30
        close_btn.Margin = Thickness(5)
        close_btn.Click += close_shop
        stack.Children.Add(close_btn)

    def close_shop(sender, e):
        global shop_window, is_paused
        if shop_window:
            shop_window.Close()
            shop_window = None
        is_paused = False
        pause_button.Content = u"Пауза"
        timer.Start()

    build_shop_ui()
    shop_window.ShowDialog()

shop_button.Click += open_shop

load_save()
update_score()
draw_field()
start_button.Visibility = System.Windows.Visibility.Visible
pause_button.IsEnabled = False
shop_button.IsEnabled = False
map_combo.IsEnabled = True

timer = DispatcherTimer()
timer.Interval = TimeSpan.FromMilliseconds(150)
timer.Tick += on_tick

window.KeyDown += on_key_down
window.ShowDialog()
