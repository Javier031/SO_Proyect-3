from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

@dataclass
class Proc:
    name: str
    arrival: int
    burst: int

@dataclass
class Metrics:
    tf: int
    T: int
    Te: int
    I: float

class Simulator:
    def __init__(self, procs: List[Proc], policy: str, quantum: Optional[int] = None):
        self.procs = [Proc(p.name, p.arrival, p.burst) for p in procs]
        self.policy = policy
        self.quantum = quantum if policy == "RR" else None

        self.remaining: Dict[str, int] = {p.name: p.burst for p in self.procs}
        self.arrival: Dict[str, int]   = {p.name: p.arrival for p in self.procs}
        self.burst: Dict[str, int]     = {p.name: p.burst for p in self.procs}
        self.finished: Dict[str, bool] = {p.name: False for p in self.procs}

        self.timeline_marks: Dict[Tuple[str, int], str] = {}
        self.tf: Dict[str, int] = {}

        self.t = 0
        self.ready: List[str] = []
        self.current: Optional[str] = None
        self.slice_left: int = self.quantum if self.quantum else 0

        self.rr_requeue: List[str] = []

        self.rows: List[str] = sorted([p.name for p in self.procs])
        self.total_finished = 0

    def _enqueue_arrivals(self):
        arriving = [p.name for p in self.procs if p.arrival == self.t]
        for p in sorted(arriving):
            self.ready.append(p)

    def _apply_rr_requeue(self):
        if self.policy == "RR" and self.rr_requeue:
            self.ready.extend(self.rr_requeue)
            self.rr_requeue.clear()

    def _sort_ready_if_sjf(self):
        if self.policy == "SJF" and self.ready:
            self.ready.sort(key=lambda p: (self.burst[p], p))

    def _select_next_if_idle(self):
        if self.current is not None or not self.ready:
            return
        if self.policy in ("FCFS", "SJF"):
            self.current = self.ready.pop(0)
        elif self.policy == "RR":
            self.current = self.ready.pop(0)
            self.slice_left = self.quantum

    def _mark_queue_positions(self):
        for i, p in enumerate(self.ready):
            self.timeline_marks[(p, self.t)] = str(i + 1)

    def _tick_execute(self):
        if self.current is None:
            return
        self.timeline_marks[(self.current, self.t)] = "X"

        self.remaining[self.current] -= 1
        if self.policy == "RR":
            self.slice_left -= 1

        if self.remaining[self.current] == 0:
            self.finished[self.current] = True
            self.tf[self.current] = self.t + 1
            self.total_finished += 1
            self.current = None
            return

        if self.policy == "RR" and self.slice_left == 0:
            self.rr_requeue.append(self.current)
            self.current = None

    def step(self) -> bool:
        self._enqueue_arrivals()
        self._apply_rr_requeue()
        self._sort_ready_if_sjf()
        self._select_next_if_idle()
        self._sort_ready_if_sjf()
        self._mark_queue_positions()
        self._tick_execute()
        self.t += 1
        return self.total_finished != len(self.rows)

    def metrics(self) -> Dict[str, Metrics]:
        out: Dict[str, Metrics] = {}
        for p in self.rows:
            tf = self.tf[p]
            ti = self.arrival[p]
            t_cpu = self.burst[p]
            T = tf - ti
            Te = T - t_cpu
            I = (t_cpu / T) if T > 0 else float('nan')
            out[p] = Metrics(tf=tf, T=T, Te=Te, I=I)
        return out
