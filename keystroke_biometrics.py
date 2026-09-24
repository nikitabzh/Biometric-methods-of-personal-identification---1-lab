"""
Лабораторная работа №1: Клавиатурный почерк. Исследование особенностей.
Программа для сбора и анализа биометрических параметров клавиатурного ввода.
С сохранением и автозагрузкой истории в JSON-файл.
"""

import json
import math
import os
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Имя файла для персистентного хранения истории измерений
DATA_FILE = "keystroke_history.json"


class KeystrokeAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Биометрия: Исследование клавиатурного почерка")
        self.root.geometry("1100x840")

        # Переменные интерфейса
        self.phrase_var = tk.StringVar(value="биометрическая защита информации")
        self.session_time_var = tk.StringVar(value="Утро")
        self.keyboard_type_var = tk.StringVar(value="Встроенная (Ноутбук)")

        # Временное хранение нажатий текущего ввода
        self.active_keys = {}
        self.current_attempt_events = []

        # База накопленных попыток
        self.records = []

        self._build_ui()
        self.update_phrase_complexity()

        # Автоматическая загрузка сохраненных измерений при запуске
        self.load_history()

    def _build_ui(self):
        # 1. Верхняя панель: Настройки эксперимента
        top_frame = ttk.LabelFrame(self.root, text="Параметры эксперимента", padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(top_frame, text="Парольная фраза:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        phrase_entry = ttk.Entry(top_frame, textvariable=self.phrase_var, width=38)
        phrase_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        phrase_entry.bind("<KeyRelease>", lambda e: self.update_phrase_complexity())

        ttk.Label(top_frame, text="Время суток:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        session_combo = ttk.Combobox(
            top_frame, textvariable=self.session_time_var,
            values=["Утро", "День", "Вечер", "Ночь"], width=10, state="readonly"
        )
        session_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        ttk.Label(top_frame, text="Клавиатура:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        kb_combo = ttk.Combobox(
            top_frame, textvariable=self.keyboard_type_var,
            values=["Встроенная (Ноутбук)", "Внешняя (Мембранная)", "Механическая"], width=22, state="readonly"
        )
        kb_combo.grid(row=0, column=5, sticky=tk.W, padx=5, pady=2)

        self.lbl_complexity = ttk.Label(top_frame, text="", foreground="#004488", font=("Segoe UI", 9, "bold"))
        self.lbl_complexity.grid(row=1, column=0, columnspan=6, sticky=tk.W, padx=5, pady=5)

        # 2. Панель ввода парольной фразы
        input_frame = ttk.LabelFrame(self.root, text="Поле для набора пароля", padding=10)
        input_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(input_frame, text="Наберите заданную фразу строго без ошибок и нажмите Enter:").pack(anchor=tk.W)
        self.input_entry = ttk.Entry(input_frame, font=("Courier New", 12), width=70)
        self.input_entry.pack(anchor=tk.W, pady=5, fill=tk.X)

        self.input_entry.bind("<KeyPress>", self.on_key_press)
        self.input_entry.bind("<KeyRelease>", self.on_key_release)
        self.input_entry.bind("<Return>", self.on_submit_attempt)

        btn_box = ttk.Frame(input_frame)
        btn_box.pack(anchor=tk.W, pady=2)
        ttk.Button(btn_box, text="Зафиксировать попытку (Enter)", command=self.on_submit_attempt).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Сбросить ввод", command=self.clear_current_input).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Очистить всю базу", command=self.reset_all_data).pack(side=tk.LEFT, padx=5)

        self.lbl_status = ttk.Label(input_frame, text="Сохранено попыток: 0", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(anchor=tk.E)

        # 3. Вкладки визуализации с Matplotlib
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 1) Динамика ввода (интервалы Down-Down)
        self.tab_flight = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_flight, text="Динамика ввода (Интервалы)")
        self.fig_flight = Figure(figsize=(8, 4), dpi=100)
        self.canvas_flight = FigureCanvasTkAgg(self.fig_flight, master=self.tab_flight)
        self.canvas_flight.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 2) Скорость (WPM / зн/с) + M[X], D[X]
        self.tab_speed = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_speed, text="Гистограмма скорости (M[X], D[X])")
        self.fig_speed = Figure(figsize=(8, 4), dpi=100)
        self.canvas_speed = FigureCanvasTkAgg(self.fig_speed, master=self.tab_speed)
        self.canvas_speed.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 3) Время удержания (Hold Time)
        self.tab_hold = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_hold, text="Время удержания (Hold Time)")
        self.fig_hold = Figure(figsize=(8, 4), dpi=100)
        self.canvas_hold = FigureCanvasTkAgg(self.fig_hold, master=self.tab_hold)
        self.canvas_hold.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 4) Наложения клавиш
        self.tab_overlaps = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_overlaps, text="Наложения клавиш (Тип 1, 2, 3)")
        self.fig_overlaps = Figure(figsize=(8, 4), dpi=100)
        self.canvas_overlaps = FigureCanvasTkAgg(self.fig_overlaps, master=self.tab_overlaps)
        self.canvas_overlaps.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------------- Оценка сложности фразы ----------------
    def update_phrase_complexity(self):
        phrase = self.phrase_var.get()
        L = len(phrase)
        if L == 0:
            self.lbl_complexity.config(text="Фраза пуста")
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

        entropy = L * math.log2(A)
        self.lbl_complexity.config(
            text=f"Длина (L): {L} симв. | Мощность алфавита (A): {A} | Энтропия (S): {entropy:.2f} бит | "
                 f"Сложность перебора: {A}^{L} (≈ 10^{L * math.log10(A):.1f})"
        )

    # ---------------- Регистрация событий клавиатуры ----------------
    def on_key_press(self, event):
        t = event.time / 1000.0
        key = event.char
        if not key or (ord(key) < 32 and ord(key) != 13):
            return
        if key not in self.active_keys:
            self.active_keys[key] = t

    def on_key_release(self, event):
        t = event.time / 1000.0
        key = event.char
        if key in self.active_keys:
            t_down = self.active_keys.pop(key)
            self.current_attempt_events.append({
                'key': key,
                'down': t_down,
                'up': t,
                'hold': max(0.001, t - t_down)
            })

    def clear_current_input(self):
        self.active_keys.clear()
        self.current_attempt_events.clear()
        self.input_entry.delete(0, tk.END)

    # ---------------- Сохранение и загрузка истории (JSON) ----------------
    def save_history(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить данные: {e}")

    def load_history(self):
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    # При чтении из JSON ключи словарей приводятся к строкам, восстанавливаем int для наложений
                    for record in data:
                        if 'overlaps' in record:
                            record['overlaps'] = {int(k): v for k, v in record['overlaps'].items()}
                    self.records = data
                    self.lbl_status.config(text=f"Сохранено попыток: {len(self.records)}")
                    self.redraw_all_plots()
        except Exception as e:
            print(f"Ошибка при загрузке истории: {e}")

    def reset_all_data(self):
        if not self.records:
            return
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить ВСЮ историю измерений из файла?"):
            self.records.clear()
            self.clear_current_input()
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            self.lbl_status.config(text="Сохранено попыток: 0")
            # Очистка холстов
            for fig, canvas in [
                (self.fig_flight, self.canvas_flight),
                (self.fig_speed, self.canvas_speed),
                (self.fig_hold, self.canvas_hold),
                (self.fig_overlaps, self.canvas_overlaps)
            ]:
                fig.clear()
                canvas.draw()

    # ---------------- Завершение попытки ввода ----------------
    def on_submit_attempt(self, event=None):
        typed_text = self.input_entry.get()
        target_phrase = self.phrase_var.get()

        if typed_text != target_phrase:
            messagebox.showwarning(
                "Ошибка набора",
                "Введенная строка не совпадает с эталонной фразой!\n"
                "Для чистоты биометрического анализа повторите попытку без ошибок."
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

    # ---------------- Анализ наложений ----------------
    def detect_overlaps(self, events):
        counts = {1: 0, 2: 0, 3: 0}
        n = len(events)
        for i in range(n - 1):
            e1 = events[i]
            e2 = events[i + 1]
            d1, u1 = e1['down'], e1['up']
            d2, u2 = e2['down'], e2['up']

            if d2 < u1:
                if u1 < u2:
                    counts[1] += 1
                elif u2 <= u1:
                    counts[3] += 1
        return counts

    # ---------------- Отрисовка графиков Matplotlib ----------------
    def redraw_all_plots(self):
        if not self.records:
            return

        last_record = self.records[-1]
        events = last_record['events']

        # 1. График динамики ввода (интервалы времени соседних символов)
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

        # 2. Гистограмма скорости ввода и стат. параметры (M[X], D[X])
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
    app = KeystrokeAnalyzerApp(root)
    root.mainloop()