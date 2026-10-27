"""
Лабораторная работа №1: Клавиатурный почерк. Парольная аутентификация.
Вариант №1: Генератор паролей длины L из алфавита A + оценка сложности (слабая, средняя, высокая)
+ биометрический анализ клавиатурного ввода (Hold time, Flight time, наложения 1-3 типов, Matplotlib, JSON).
"""

import json
import math
import os
import random
import string
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

DATA_FILE = "keystroke_history.json"


class KeystrokeBiometricsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Лабораторная работа №1: Парольная аутентификация и биометрия почерка (Вариант 1)")
        self.root.geometry("1140x880")

        # Переменные генератора паролей (Вариант 1)
        self.phrase_var = tk.StringVar(value="ZdesParol2205#")
        self.length_var = tk.IntVar(value=14)
        self.use_lower_var = tk.BooleanVar(value=True)
        self.use_upper_var = tk.BooleanVar(value=True)
        self.use_digits_var = tk.BooleanVar(value=True)
        self.use_special_var = tk.BooleanVar(value=True)

        # Параметры биометрического эксперимента
        self.session_time_var = tk.StringVar(value="День")
        self.keyboard_type_var = tk.StringVar(value="Механическая")

        # Структуры регистрации нажатий клавиш
        self.active_keys = {}
        self.current_attempt_events = []

        # База накопленных попыток
        self.records = []

        self._build_ui()
        self.update_phrase_complexity()
        self.load_history()

    def _build_ui(self):
        # =====================================================================
        # 1. ПАНЕЛЬ ВАРИАНТА №1: ГЕНЕРАТОР ПАРОЛЕЙ И ОЦЕНКА СЛОЖНОСТИ
        # =====================================================================
        gen_frame = ttk.LabelFrame(self.root, text="Задание Варианта №1: Генерация паролей и оценка сложности", padding=10)
        gen_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # Настройки генератора
        opts_box = ttk.Frame(gen_frame)
        opts_box.pack(fill=tk.X, pady=2)

        ttk.Label(opts_box, text="Длина (L):").pack(side=tk.LEFT, padx=3)
        spin_len = ttk.Spinbox(opts_box, from_=4, to=64, textvariable=self.length_var, width=5)
        spin_len.pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(opts_box, text="a-z (26)", variable=self.use_lower_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts_box, text="A-Z (26)", variable=self.use_upper_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts_box, text="0-9 (10)", variable=self.use_digits_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts_box, text="Спецсимволы (32)", variable=self.use_special_var).pack(side=tk.LEFT, padx=5)

        ttk.Button(opts_box, text="Сгенерировать пароль (L, A)", command=self.generate_random_password).pack(side=tk.LEFT, padx=15)

        # Строка парольной фразы
        phrase_box = ttk.Frame(gen_frame)
        phrase_box.pack(fill=tk.X, pady=4)

        ttk.Label(phrase_box, text="Парольная фраза:").pack(side=tk.LEFT, padx=3)
        entry_phrase = ttk.Entry(phrase_box, textvariable=self.phrase_var, font=("Courier New", 11), width=40)
        entry_phrase.pack(side=tk.LEFT, padx=5)
        entry_phrase.bind("<KeyRelease>", lambda e: self.update_phrase_complexity())

        ttk.Label(phrase_box, text="Время суток:").pack(side=tk.LEFT, padx=(15, 3))
        combo_time = ttk.Combobox(phrase_box, textvariable=self.session_time_var, values=["Утро", "День", "Вечер", "Ночь"], width=8, state="readonly")
        combo_time.pack(side=tk.LEFT, padx=3)

        ttk.Label(phrase_box, text="Клавиатура:").pack(side=tk.LEFT, padx=(15, 3))
        combo_kb = ttk.Combobox(phrase_box, textvariable=self.keyboard_type_var, values=["Механическая", "Встроенная (Ноутбук)", "Внешняя (Мембранная)"], width=22, state="readonly")
        combo_kb.pack(side=tk.LEFT, padx=3)

        # Информационная строка сложности
        self.lbl_complexity = ttk.Label(gen_frame, text="", font=("Segoe UI", 9, "bold"))
        self.lbl_complexity.pack(anchor=tk.W, pady=3)

        # =====================================================================
        # 2. ПАНЕЛЬ ВВОДА ДЛЯ ИССЛЕДОВАНИЯ КЛАВИАТУРНОГО ПОЧЕРКА
        # =====================================================================
        input_frame = ttk.LabelFrame(self.root, text="Исследование клавиатурного ввода", padding=10)
        input_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(input_frame, text="Наберите заданную парольную фразу строго без ошибок и нажмите Enter:").pack(anchor=tk.W)
        self.input_entry = ttk.Entry(input_frame, font=("Courier New", 12), width=70)
        self.input_entry.pack(anchor=tk.W, pady=5, fill=tk.X)

        self.input_entry.bind("<KeyPress>", self.on_key_press)
        self.input_entry.bind("<KeyRelease>", self.on_key_release)
        self.input_entry.bind("<Return>", self.on_submit_attempt)

        btn_box = ttk.Frame(input_frame)
        btn_box.pack(anchor=tk.W, pady=2)
        ttk.Button(btn_box, text="Зафиксировать попытку (Enter)", command=self.on_submit_attempt).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Сбросить ввод", command=self.clear_current_input).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Очистить всю базу измерений", command=self.reset_all_data).pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(input_frame, text="Сохранено попыток: 0", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(anchor=tk.E)

        # =====================================================================
        # 3. ВКЛАДКИ ВИЗУАЛИЗАЦИИ РЕЗУЛЬТАТОВ (MATPLOTLIB)
        # =====================================================================
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 1. Динамика ввода
        self.tab_flight = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_flight, text="Динамика ввода (Интервалы)")
        self.fig_flight = Figure(figsize=(8, 4), dpi=100)
        self.canvas_flight = FigureCanvasTkAgg(self.fig_flight, master=self.tab_flight)
        self.canvas_flight.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 2. Скорость + M[X], D[X]
        self.tab_speed = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_speed, text="Гистограмма скорости (M[X], D[X])")
        self.fig_speed = Figure(figsize=(8, 4), dpi=100)
        self.canvas_speed = FigureCanvasTkAgg(self.fig_speed, master=self.tab_speed)
        self.canvas_speed.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 3. Время удержания
        self.tab_hold = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_hold, text="Время удержания (Hold Time)")
        self.fig_hold = Figure(figsize=(8, 4), dpi=100)
        self.canvas_hold = FigureCanvasTkAgg(self.fig_hold, master=self.tab_hold)
        self.canvas_hold.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 4. Наложения
        self.tab_overlaps = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_overlaps, text="Наложения клавиш (Тип 1, 2, 3)")
        self.fig_overlaps = Figure(figsize=(8, 4), dpi=100)
        self.canvas_overlaps = FigureCanvasTkAgg(self.fig_overlaps, master=self.tab_overlaps)
        self.canvas_overlaps.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------------- ГЕНЕРАТОР ПАРОЛЕЙ (ВАРИАНТ №1) ----------------
    def generate_random_password(self):
        alphabet = ""
        if self.use_lower_var.get():
            alphabet += string.ascii_lowercase
        if self.use_upper_var.get():
            alphabet += string.ascii_uppercase
        if self.use_digits_var.get():
            alphabet += string.digits
        if self.use_special_var.get():
            alphabet += "!@#$%^&*()-_=+[]{}|;:,.<>?"

        if not alphabet:
            messagebox.showwarning("Ошибка", "Выберите хотя бы один набор символов алфавита!")
            return

        L = max(4, self.length_var.get())
        new_password = "".join(random.choice(alphabet) for _ in range(L))
        self.phrase_var.set(new_password)
        self.update_phrase_complexity()

    # ---------------- ОЦЕНКА СЛОЖНОСТИ ПАРОЛЬНОЙ ФРАЗЫ ----------------
    def update_phrase_complexity(self):
        phrase = self.phrase_var.get()
        L = len(phrase)
        if L == 0:
            self.lbl_complexity.config(text="Фраза пуста", foreground="gray")
            return

        has_lower_ru = any('а' <= c <= 'я' or c == 'ё' for c in phrase)
        has_upper_ru = any('А' <= c <= 'Я' or c == 'Ё' for c in phrase)
        has_lower_en = any('a' <= c <= 'z' for c in phrase)
        has_upper_en = any('A' <= c <= 'Z' for c in phrase)
        has_digits = any(c.isdigit() for c in phrase)
        has_special = any(not c.isalnum() for c in phrase)

        A = 0
        if has_lower_ru: A += 33
        if has_upper_ru: A += 33
        if has_lower_en: A += 26
        if has_upper_en: A += 26
        if has_digits: A += 10
        if has_special: A += 32
        if A == 0: A = 1

        # Формула Хартли: H = L * log2(A)
        H = L * math.log2(A)

        # Классификация сложности (слабая, средняя, высокая) согласно Варианту 1
        if H < 60 or L < 8:
            level = "Слабая"
            color = "#D32F2F"  # Красный
        elif H < 85:
            level = "Средняя"
            color = "#F57C00"  # Оранжевый
        else:
            level = "Высокая"
            color = "#2E7D32"  # Зеленый

        self.lbl_complexity.config(
            text=f"Сложность: [{level}] | Длина (L): {L} симв. | Алфавит (A): {A} | "
                 f"Энтропия (H): {H:.1f} бит | Комбинаций (S=A^L): {A}^{L} (≈ 10^{L * math.log10(A):.1f})",
            foreground=color
        )

    # ---------------- ОБРАБОТЧИКИ НАЖАТИЯ КЛАВИШ ----------------
    def on_key_press(self, event):
        t = event.time / 1000.0
        k = event.char
        if not k or (ord(k) < 32 and ord(k) != 13):
            return
        if k not in self.active_keys:
            self.active_keys[k] = t

    def on_key_release(self, event):
        t = event.time / 1000.0
        k = event.char
        if k in self.active_keys:
            t_down = self.active_keys.pop(k)
            self.current_attempt_events.append({
                'key': k,
                'down': t_down,
                'up': t,
                'hold': max(0.001, t - t_down)
            })

    def clear_current_input(self):
        self.active_keys.clear()
        self.current_attempt_events.clear()
        self.input_entry.delete(0, tk.END)

    # ---------------- СОХРАНЕНИЕ / ЗАГРУЗКА ИСТОРИИ (JSON) ----------------
    def save_history(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить данные: {e}")

    def load_history(self):
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for record in data:
                        if 'overlaps' in record:
                            record['overlaps'] = {int(k): v for k, v in record['overlaps'].items()}
                    self.records = data
                    self.lbl_status.config(text=f"Сохранено попыток: {len(self.records)}")
                    self.redraw_all_plots()
        except Exception as e:
            print(f"Ошибка загрузки истории: {e}")

    def reset_all_data(self):
        if not self.records:
            return
        if messagebox.askyesno("Подтверждение", "Удалить ВСЮ накопленную историю измерений из файла?"):
            self.records.clear()
            self.clear_current_input()
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            self.lbl_status.config(text="Сохранено попыток: 0")
            for fig, canvas in [
                (self.fig_flight, self.canvas_flight),
                (self.fig_speed, self.canvas_speed),
                (self.fig_hold, self.canvas_hold),
                (self.fig_overlaps, self.canvas_overlaps)
            ]:
                fig.clear()
                canvas.draw()

    # ---------------- ОБРАБОТКА ПОПЫТКИ ВВОДА ----------------
    def on_submit_attempt(self, event=None):
        typed_text = self.input_entry.get()
        target_phrase = self.phrase_var.get()

        if typed_text != target_phrase:
            messagebox.showwarning(
                "Ошибка набора",
                "Введенная строка не совпадает с эталонной фразой!\nПовторите ввод строго без ошибок."
            )
            self.clear_current_input()
            return

        if len(self.current_attempt_events) < 2:
            messagebox.showwarning("Ошибка", "Недостаточно данных для анализа!")
            self.clear_current_input()
            return

        events = sorted(self.current_attempt_events, key=lambda x: x['down'])
        t_start = events[0]['down']
        t_end = max(e['up'] for e in events)
        total_time = max(0.001, t_end - t_start)
        speed_cps = len(target_phrase) / total_time

        overlaps = self.detect_overlaps(events)

        record = {
            'session': self.session_time_var.get(),
            'kb': self.keyboard_type_var.get(),
            'speed': speed_cps,
            'events': events,
            'overlaps': overlaps
        }
        self.records.append(record)
        self.save_history()

        self.lbl_status.config(text=f"Сохранено попыток: {len(self.records)}")
        self.clear_current_input()
        self.redraw_all_plots()

    # ---------------- ДЕТЕКЦИЯ НАЛОЖЕНИЙ (ТИП 1, 2, 3) ----------------
    def detect_overlaps(self, events):
        """
        Классификация наложений согласно методичке:
        Тип 1: K1↓ -> K2↓ -> K1↑ -> K2↑ (d1 <= d2 < u1 < u2)
        Тип 2: K2↓ -> K1↓ -> K2↑ -> K1↑ (обратный порядок отпускания)
        Тип 3: K1 внутри K2 (d1 <= d2 < u2 <= u1)
        """
        counts = {1: 0, 2: 0, 3: 0}
        n = len(events)
        for i in range(n - 1):
            e1 = events[i]
            e2 = events[i + 1]
            d1, u1 = e1['down'], e1['up']
            d2, u2 = e2['down'], e2['up']

            if d2 < u1:
                # Вторая клавиша нажата до отпускания первой
                if d1 <= d2 and u1 < u2:
                    counts[1] += 1
                elif d1 <= d2 and u2 <= u1:
                    counts[3] += 1

            if u2 < u1 and d2 < u2:
                if not (d1 <= d2 and u2 <= u1):
                    counts[2] += 1

        return counts

    # ---------------- ОТРИСОВКА ГРАФИКОВ (MATPLOTLIB) ----------------
    def redraw_all_plots(self):
        if not self.records:
            return

        last_record = self.records[-1]
        events = last_record['events']

        # 1. Динамика ввода (Down-Down интервалы)
        self.fig_flight.clear()
        ax_fl = self.fig_flight.add_subplot(111)
        intervals = []
        labels = []
        for i in range(len(events) - 1):
            dt = (events[i+1]['down'] - events[i]['down']) * 1000.0
            intervals.append(dt)
            labels.append(f"{events[i]['key']}→{events[i+1]['key']}")

        x = np.arange(len(intervals))
        ax_fl.plot(x, intervals, marker='o', color='#0066cc', linewidth=2)
        ax_fl.set_xticks(x)
        ax_fl.set_xticklabels(labels, rotation=90, fontsize=8)
        ax_fl.set_ylabel("Интервал (Down-Down), мс")
        ax_fl.set_title(f"Динамика ввода последней попытки (Клавиатура: {last_record['kb']})")
        ax_fl.grid(True, linestyle='--', alpha=0.6)
        self.fig_flight.tight_layout()
        self.canvas_flight.draw()

        # 2. Гистограмма скорости + M[X], D[X]
        self.fig_speed.clear()
        ax_sp = self.fig_speed.add_subplot(111)

        speeds = [r['speed'] for r in self.records]
        m_speed = float(np.mean(speeds))
        d_speed = float(np.var(speeds)) if len(speeds) > 1 else 0.0

        sessions = {}
        for r in self.records:
            sessions.setdefault(r['session'], []).append(r['speed'])

        labels_sess = []
        means_sess = []
        vars_sess = []
        for s_name, s_speeds in sessions.items():
            labels_sess.append(s_name)
            means_sess.append(float(np.mean(s_speeds)))
            vars_sess.append(float(np.var(s_speeds)) if len(s_speeds) > 1 else 0.0)

        x_bar = np.arange(len(labels_sess))
        ax_sp.bar(x_bar, means_sess, yerr=[np.sqrt(v) for v in vars_sess], capsize=5, color='#4CAF50', alpha=0.8)
        ax_sp.set_xticks(x_bar)
        ax_sp.set_xticklabels(labels_sess)
        ax_sp.set_ylabel("Скорость ввода (символов/сек)")
        ax_sp.set_title(f"Всего попыток: {len(speeds)} | Общее M[X] = {m_speed:.2f} симв/с, D[X] = {d_speed:.4f}")
        ax_sp.grid(axis='y', linestyle='--', alpha=0.6)
        self.fig_speed.tight_layout()
        self.canvas_speed.draw()

        # 3. Время удержания клавиш (Hold time)
        self.fig_hold.clear()
        ax_hd = self.fig_hold.add_subplot(111)
        keys_list = [e['key'] for e in events]
        holds_list = [e['hold'] * 1000.0 for e in events]
        ax_hd.bar(np.arange(len(keys_list)), holds_list, color='#FF9800', alpha=0.85)
        ax_hd.set_xticks(np.arange(len(keys_list)))
        ax_hd.set_xticklabels(keys_list, fontsize=9)
        ax_hd.set_ylabel("Время удержания (Hold Time), мс")
        ax_hd.set_title(f"Время удержания каждой клавиши (Среднее = {float(np.mean(holds_list)):.1f} мс)")
        ax_hd.grid(axis='y', linestyle='--', alpha=0.6)
        self.fig_hold.tight_layout()
        self.canvas_hold.draw()

        # 4. Наложения
        self.fig_overlaps.clear()
        ax_ov = self.fig_overlaps.add_subplot(111)
        cur_kb = last_record['kb']
        kb_records = [r for r in self.records if r['kb'] == cur_kb]
        sum_t1 = sum(r['overlaps'].get(1, 0) for r in kb_records)
        sum_t2 = sum(r['overlaps'].get(2, 0) for r in kb_records)
        sum_t3 = sum(r['overlaps'].get(3, 0) for r in kb_records)

        types = ['Тип 1 (K1↓ K2↓ K1↑ K2↑)', 'Тип 2 (K2↓ K1↓ K2↑ K1↑)', 'Тип 3 (K1 внутри K2)']
        counts = [sum_t1, sum_t2, sum_t3]
        ax_ov.bar(types, counts, color=['#2196F3', '#9C27B0', '#E91E63'])
        ax_ov.set_ylabel("Суммарное количество наложений")
        ax_ov.set_title(f"Наложения для клавиатуры: {cur_kb} ({len(kb_records)} попыток в базе)")
        for i, val in enumerate(counts):
            ax_ov.text(i, val + 0.1, str(val), ha='center', fontweight='bold')
        ax_ov.grid(axis='y', linestyle='--', alpha=0.6)
        self.fig_overlaps.tight_layout()
        self.canvas_overlaps.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = KeystrokeBiometricsApp(root)
    root.mainloop()