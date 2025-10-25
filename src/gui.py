
import math
import tkinter as tk
from tkinter import ttk, messagebox

from .simulator import Simulator, Proc
from .utils import (
    TICK_MS_DEFAULT, GRID_LINE, GRID_LINE_BOLD, TEXT_MAIN, TEXT_MUTED,
    RUN_FILL, BEST_ROW, AVG_ROW, CANVAS_BG, FONT_LABEL, FONT_TIME, FONT_CELL, FONT_LEGEND
)

class App(tk.Tk):
    CELL_W = 28
    CELL_H = 26
    LEFT_MARGIN = 100
    TOP_MARGIN = 70
    GRID_PAD = 16

    def __init__(self):
        super().__init__()
        self.title("Simulador de Planificación de CPU – FCFS / SJF / RR")
        self.geometry("1160x760")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except:
            pass
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", "#E0EBFF")])

        self.procs = []
        self.sim = None
        self.running = False
        self.total_cols = 0

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=12, pady=8)

        ttk.Label(top, text="Proceso").grid(row=0, column=0, padx=4)
        self.ent_name = ttk.Entry(top, width=8)
        self.ent_name.grid(row=0, column=1, padx=4)

        ttk.Label(top, text="Llegada (ti)").grid(row=0, column=2, padx=4)
        self.ent_arrival = ttk.Entry(top, width=6)
        self.ent_arrival.grid(row=0, column=3, padx=4)

        ttk.Label(top, text="CPU (t)").grid(row=0, column=4, padx=4)
        self.ent_burst = ttk.Entry(top, width=6)
        self.ent_burst.grid(row=0, column=5, padx=4)

        ttk.Button(top, text="Agregar", command=self.add_proc).grid(row=0, column=6, padx=8)
        ttk.Button(top, text="Eliminar seleccionado", command=self.del_selected).grid(row=0, column=7, padx=6)
        ttk.Button(top, text="Limpiar lista", command=self.clear_list).grid(row=0, column=8, padx=6)

        cols = ("name", "arrival", "burst")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, w, txt in zip(cols, (90, 120, 100), ("Proceso", "Llegada (ti)", "CPU (t)")):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor=tk.CENTER)
        self.tree.pack(fill=tk.X, padx=12)

        alg = ttk.Frame(self)
        alg.pack(fill=tk.X, padx=12, pady=8)

        self.alg_var = tk.StringVar(value="FCFS")
        for i, name in enumerate(("FCFS", "SJF", "RR")):
            ttk.Radiobutton(alg, text=name, value=name, variable=self.alg_var,
                            command=self._on_alg_change).grid(row=0, column=i, padx=8)

        ttk.Label(alg, text="Quantum (solo RR):").grid(row=0, column=3, padx=(20,6))
        self.ent_quantum = ttk.Entry(alg, width=6, state="disabled")
        self.ent_quantum.grid(row=0, column=4)

        ttk.Label(alg, text="Velocidad (ms/tick):").grid(row=0, column=5, padx=(20,6))
        self.ent_tick = ttk.Entry(alg, width=8)
        self.ent_tick.insert(0, str(TICK_MS_DEFAULT))
        self.ent_tick.grid(row=0, column=6)

        self.btn_run = ttk.Button(alg, text="Iniciar Simulación", command=self.run_simulation)
        self.btn_run.grid(row=0, column=7, padx=10)
        self.btn_pause = ttk.Button(alg, text="Pausar", command=self.toggle_pause, state="disabled")
        self.btn_pause.grid(row=0, column=8, padx=6)
        self.btn_reset = ttk.Button(alg, text="Reiniciar Vista", command=self.reset_view, state="disabled")
        self.btn_reset.grid(row=0, column=9, padx=6)

        mid = ttk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        self.canvas = tk.Canvas(mid, bg=CANVAS_BG, height=400, highlightthickness=0)
        self.hscroll = ttk.Scrollbar(mid, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.hscroll.set)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.hscroll.pack(side=tk.TOP, fill=tk.X)

        self.legend = ttk.Label(self, text="Leyenda:  X = en CPU   |   números = posición en cola (1=primero)",
                                foreground=TEXT_MUTED, font=FONT_LEGEND)
        self.legend.pack(anchor="w", padx=14, pady=(0,6))

        rr_frame = ttk.LabelFrame(self, text="Cola (Round Robin)")
        rr_frame.pack(fill=tk.X, padx=12, pady=(0,6))
        self.rr_label = ttk.Label(rr_frame, text="(Visible solo en RR)", foreground=TEXT_MUTED)
        self.rr_label.pack(anchor="w", padx=8, pady=4)

        self.results_frame = ttk.LabelFrame(self, text="Resultados")
        self.results_tree = None
        self.avg_label = None

    def add_proc(self):
        name = self.ent_name.get().strip()
        ti = self.ent_arrival.get().strip()
        t = self.ent_burst.get().strip()
        if not name:
            messagebox.showerror("Error", "Ingrese el nombre del proceso.")
            return
        if not ti.isdigit() or not t.isdigit():
            messagebox.showerror("Error", "Llegada y CPU deben ser enteros no negativos.")
            return
        ti, t = int(ti), int(t)
        if any(p.name == name for p in self.procs):
            messagebox.showerror("Error", "El nombre del proceso debe ser único.")
            return
        if ti < 0 or t < 1:
            messagebox.showerror("Error", "Llegada ≥ 0 y CPU ≥ 1.")
            return
        self.procs.append(Proc(name, ti, t))
        self._refresh_tree()
        self.ent_name.delete(0, tk.END); self.ent_arrival.delete(0, tk.END); self.ent_burst.delete(0, tk.END)

    def del_selected(self):
        sel = self.tree.selection()
        if not sel: return
        name = self.tree.item(sel[0], "values")[0]
        self.procs = [p for p in self.procs if p.name != name]
        self._refresh_tree()

    def clear_list(self):
        self.procs.clear()
        self._refresh_tree()

    def _refresh_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for p in sorted(self.procs, key=lambda x: x.name):
            self.tree.insert("", tk.END, values=(p.name, p.arrival, p.burst))

    def _on_alg_change(self):
        self.ent_quantum.configure(state=("normal" if self.alg_var.get()=="RR" else "disabled"))

    def run_simulation(self):
        if not self.procs:
            messagebox.showerror("Error", "Ingrese al menos un proceso."); return
        alg = self.alg_var.get()
        q = None
        if alg == "RR":
            qtxt = self.ent_quantum.get().strip()
            if not qtxt.isdigit() or int(qtxt) < 1:
                messagebox.showerror("Error", "Quantum inválido (entero ≥ 1)."); return
            q = int(qtxt)
        tick = self.ent_tick.get().strip()
        if not tick.isdigit() or int(tick) < 100:
            messagebox.showerror("Error", "Velocidad inválida (ms/tick ≥ 100)."); return
        self.current_tick_ms = int(tick)

        self.reset_view(keep_processes=True, silent=True)

        preview = Simulator(self.procs, alg, quantum=q)
        while preview.step(): pass
        self.total_cols = preview.t

        self.sim = Simulator(self.procs, alg, quantum=q)
        self._init_canvas_grid(full_cols=self.total_cols)

        self.btn_run.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_reset.configure(state="disabled")
        self.running = True
        self._tick_loop()

    def _tick_loop(self):
        if not self.running or self.sim is None: return
        cont = self.sim.step()
        col = self.sim.t - 1
        if col >= 0: self._draw_marks_in_column(col)

        if self.sim.policy == "RR":
            cola_txt = "Cola actual: " + (" → ".join(self.sim.ready) if self.sim.ready else "(vacía)")
            if self.sim.current: cola_txt += f"   |   Ejecutando: {self.sim.current}"
            self.rr_label.configure(text=cola_txt)
        else:
            self.rr_label.configure(text="(Visible solo en RR)")

        if cont:
            self.after(self.current_tick_ms, self._tick_loop)
        else:
            self.running = False
            self.btn_pause.configure(state="disabled")
            self.btn_reset.configure(state="normal")
            self._show_results()

    def toggle_pause(self):
        if self.sim is None: return
        self.running = not self.running
        self.btn_pause.configure(text=("Pausar" if self.running else "Reanudar"))
        if self.running: self._tick_loop()

    def reset_view(self, keep_processes=True, silent=False):
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0,0,0,0))
        self.rr_label.configure(text="(Visible solo en RR)")
        self.sim = None; self.running = False; self.total_cols = 0
        self.btn_pause.configure(text="Pausar", state="disabled")
        self.btn_reset.configure(state="disabled")
        self.btn_run.configure(state="normal")
        self._clear_results()
        if not keep_processes: self.clear_list()
        if not silent: messagebox.showinfo("Listo", "Vista reiniciada. Puedes ejecutar otro algoritmo con los mismos procesos.")

    def _clear_results(self):
        for child in self.results_frame.winfo_children(): child.destroy()
        self.results_frame.pack_forget()
        self.results_tree = None; self.avg_label = None

    def _init_canvas_grid(self, full_cols: int):
        if self.sim is None: return
        rows = self.sim.rows

        for i, name in enumerate(rows):
            y = self.TOP_MARGIN + i*self.CELL_H
            self.canvas.create_text(self.LEFT_MARGIN-14, y + self.CELL_H/2, text=name,
                                    anchor="e", font=FONT_LABEL, fill=TEXT_MAIN)

        self.canvas.create_text(self.LEFT_MARGIN, self.TOP_MARGIN - 32, text="Tiempo",
                                anchor="w", font=FONT_LABEL, fill=TEXT_MAIN)

        for col in range(full_cols):
            x0 = self.LEFT_MARGIN + col*self.CELL_W
            x1 = x0 + self.CELL_W

            self.canvas.create_text(x0 + self.CELL_W/2, self.TOP_MARGIN - 8,
                                    text=str(col), anchor="s", font=FONT_TIME, fill=TEXT_MUTED)

            line_color = GRID_LINE_BOLD if (col % 5 == 0) else GRID_LINE

            for i, _name in enumerate(rows):
                y0 = self.TOP_MARGIN + i*self.CELL_H
                y1 = y0 + self.CELL_H
                self.canvas.create_line(x0, y0, x0, y1, fill=line_color)
                self.canvas.create_line(x1, y0, x1, y1, fill=GRID_LINE)
                self.canvas.create_line(x0, y0, x1, y0, fill=GRID_LINE)
                self.canvas.create_line(x0, y1, x1, y1, fill=GRID_LINE)

        height = self.TOP_MARGIN + len(rows)*self.CELL_H
        last_x = self.LEFT_MARGIN + full_cols*self.CELL_W
        self.canvas.configure(scrollregion=(0, 0, last_x + self.GRID_PAD, height + self.GRID_PAD))
        self.canvas.update()

    def _draw_marks_in_column(self, col: int):
        if self.sim is None: return
        rows = self.sim.rows
        x0 = self.LEFT_MARGIN + col*self.CELL_W
        for i, name in enumerate(rows):
            y0 = self.TOP_MARGIN + i*self.CELL_H
            mark = self.sim.timeline_marks.get((name, col), "")
            if mark:
                if mark == "X":
                    self.canvas.create_rectangle(x0+1, y0+1, x0+self.CELL_W-1, y0+self.CELL_H-1,
                                                 fill=RUN_FILL, outline="")
                    self.canvas.create_text(x0 + self.CELL_W/2, y0 + self.CELL_H/2,
                                            text="X", font=FONT_CELL, fill=TEXT_MAIN)
                else:
                    self.canvas.create_text(x0 + self.CELL_W/2, y0 + self.CELL_H/2,
                                            text=mark, font=("Segoe UI", 10, "bold"),
                                            fill=TEXT_MUTED)

    def _show_results(self):
        if self.sim is None:
            return

        self._clear_results()
        metrics = self.sim.metrics()
        self.results_frame.pack(fill=tk.BOTH, expand=False, padx=12, pady=8)

        cols = ("Proceso","ti","t","tf","T","Te","I")
        self.results_tree = ttk.Treeview(self.results_frame, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (100,70,60,70,70,70,80)):
            self.results_tree.heading(c, text=c)
            self.results_tree.column(c, width=w, anchor=tk.CENTER)
        self.results_tree.pack(fill=tk.X, padx=8, pady=6)

        self.results_tree.tag_configure("odd", background="#FAFAFA")
        self.results_tree.tag_configure("even", background="#FFFFFF")

        I_values = []
        for idx, name in enumerate(self.sim.rows):
            m = metrics[name]; ti = self.sim.arrival[name]; t_cpu = self.sim.burst[name]
            tag = "odd" if idx % 2 else "even"
            self.results_tree.insert("", tk.END,
                values=(name, ti, t_cpu, m.tf, m.T, m.Te, f"{m.I:.2f}"),
                tags=(tag,))
            I_values.append((name, abs(1 - m.I)))

        avg_I = sum((metrics[n].I for n in self.sim.rows)) / len(self.sim.rows)
        avg_str = f"{avg_I:.2f}"

        self.results_tree.tag_configure("avgrow", background="#EEF3FF")
        self.results_tree.insert("", tk.END,
            values=("—","—","—","—","—","—", avg_str),
            tags=("avgrow",))

        self.avg_label = ttk.Label(
            self.results_frame,
            text=f"Promedio del índice de servicio (Ī) = {avg_str}",
            font=("Segoe UI Semibold", 10)
        )
        self.avg_label.pack(anchor="e", padx=8, pady=(0,8))

        if I_values:
            best_dist = min(d for _, d in I_values)
            best = [n for n, d in I_values if abs(d - best_dist) <= 1e-12]
            for iid in self.results_tree.get_children():
                vals = self.results_tree.item(iid, "values")
                if vals and vals[0] in best:
                    self.results_tree.tag_configure("besttag", background=BEST_ROW)
                    self.results_tree.item(iid, tags=("besttag",))
                    
        self.btn_reset.configure(state="normal")

