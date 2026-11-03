#!/usr/bin/env python3
"""Independent symbolic checker. Standard library only; no producer imports."""
import argparse
import hashlib
import itertools
import json
import platform
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


class BDD:
    def __init__(self, n, limit=1000000):
        self.n, self.limit = n, limit
        self.nodes = [(n, 0, 0), (n, 1, 1)]
        self.unique = {}
        self.free_ids = []
        self.ops, self.neg, self.cof = {}, {0: 1, 1: 0}, {}
        self.vars = [self.mk(i, 0, 1) for i in range(n)]

    def mk(self, v, lo, hi):
        if lo == hi:
            return lo
        key = (v, lo, hi)
        if key not in self.unique:
            if self.free_ids:
                node = self.free_ids.pop()
                self.nodes[node] = key
            else:
                need(len(self.nodes) < self.limit, 'BDD node budget exhausted')
                node = len(self.nodes)
                self.nodes.append(key)
                if node % 16384 == 0:
                    need(rss_bytes() < 2*1024**3, 'RSS cap')
            self.unique[key] = node
        return self.unique[key]

    def NOT(self, a):
        if a not in self.neg:
            v, lo, hi = self.nodes[a]
            b = self.mk(v, self.NOT(lo), self.NOT(hi))
            self.neg[a] = b
            self.neg[b] = a
        return self.neg[a]

    def AND(self, a, b):
        if a == 0 or b == 0:
            return 0
        if a == 1:
            return b
        if b == 1 or a == b:
            return a
        if a > b:
            a, b = b, a
        key = (a, b)
        if key not in self.ops:
            va, la, ha = self.nodes[a]
            vb, lb, hb = self.nodes[b]
            v = min(va, vb)
            if va != v:
                la = ha = a
            if vb != v:
                lb = hb = b
            self.ops[key] = self.mk(v, self.AND(la, lb), self.AND(ha, hb))
        return self.ops[key]

    def OR(self, a, b):
        return self.NOT(self.AND(self.NOT(a), self.NOT(b)))

    def restrict(self, a, v, value):
        key = (a, v, value)
        if key not in self.cof:
            w, lo, hi = self.nodes[a]
            if w > v or a < 2:
                r = a
            elif w == v:
                r = hi if value else lo
            else:
                r = self.mk(w, self.restrict(lo, v, value), self.restrict(hi, v, value))
            self.cof[key] = r
        return self.cof[key]

    def exists(self, a, v):
        return self.OR(self.restrict(a, v, 0), self.restrict(a, v, 1))

    def cube(self, assignments):
        a = 1
        for v, x in sorted(assignments.items(), reverse=True):
            a = self.mk(v, 0, a) if x else self.mk(v, a, 0)
        return a

    def image(self, states, v, formula):
        # Existentially forget OLD v separately for f=0 and f=1,
        # then constrain NEW v. No simultaneous multi-node updates.
        low = self.exists(self.AND(states, self.NOT(formula)), v)
        high = self.exists(self.AND(states, formula), v)
        return self.OR(self.AND(low, self.NOT(self.vars[v])), self.AND(high, self.vars[v]))

    def preimage(self, states, v, formula):
        return self.OR(self.AND(self.restrict(states, v, 0), self.NOT(formula)),
                       self.AND(self.restrict(states, v, 1), formula))

    def contains(self, a, bits):
        while a > 1:
            v, lo, hi = self.nodes[a]
            a = hi if (bits >> v) & 1 else lo
        return bool(a)

    def count(self, a):
        cache = {}
        def rec(a, start):
            if a < 2:
                return a << (self.n - start)
            if (a, start) not in cache:
                v, lo, hi = self.nodes[a]
                cache[a, start] = (rec(lo, v+1) + rec(hi, v+1)) << (v-start)
            return cache[a, start]
        return rec(a, 0)

    def flush(self):
        self.ops.clear()
        self.cof.clear()

    def collect(self, roots):
        """Mark/sweep without renumbering live roots. All operation caches reset."""
        live = {0,1}
        stack = list(roots) + self.vars
        while stack:
            a = stack.pop()
            if a not in live:
                live.add(a)
                _,lo,hi = self.nodes[a]
                stack.extend((lo,hi))
        self.flush()
        self.neg = {0:1,1:0}
        self.unique = {self.nodes[a]:a for a in live if a > 1}
        self.free_ids = [a for a in range(2,len(self.nodes)) if a not in live]


def kernel_test():
    b = BDD(3)
    sets = []
    for mask in range(256):
        a = 0
        for state in range(8):
            if (mask >> state) & 1:
                a = b.OR(a, b.cube({v: (state >> v) & 1 for v in range(3)}))
        need(b.count(a) == mask.bit_count(), 'kernel count')
        need(all(b.contains(a, s) == bool((mask >> s) & 1) for s in range(8)), 'kernel membership')
        sets.append(a)
    # All 3-variable sets; representative Boolean functions include self dependence.
    tests = 0
    for mask, a in enumerate(sets):
        for fm in [0, 255, 170, 204, 240, 150, 105, 128, 254, 23, 232]:
            for v in range(3):
                f = sets[fm]
                forward = {(s & ~(1 << v)) | (((fm >> s) & 1) << v)
                           for s in range(8) if (mask >> s) & 1}
                backward = {s for s in range(8) if
                            (mask >> ((s & ~(1 << v)) | (((fm >> s) & 1) << v))) & 1}
                need({s for s in range(8) if b.contains(b.image(a, v, f), s)} == forward, 'kernel image')
                need({s for s in range(8) if b.contains(b.preimage(a, v, f), s)} == backward, 'kernel preimage')
                tests += 1
    return {'state_sets': 256, 'image_preimage_pairs': tests}


class Network:
    def __init__(self):
        raw = (ROOT / 'inputs/biomodels-derived.bnet').read_bytes()
        need(hashlib.sha256(raw).hexdigest() ==
             'e15ee45915ca1ff81b363cdf24db1a4f4fab37f250e6b3e57cf8ff9ca52d744d', 'source hash')
        lines = [line.strip() for line in raw.decode().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        need(lines.pop(0) == 'targets, factors', 'bnet header')
        pairs = [line.split(',', 1) for line in lines]
        self.names = [p[0].strip() for p in pairs]
        need(len(self.names) == len(set(self.names)) == 56, '56 unique nodes')
        self.index = {name: i for i, name in enumerate(self.names)}
        self.terms = []
        for _, expr in pairs:
            terms = []
            for term in expr.split('|'):
                literals = []
                for literal in term.split('&'):
                    s = literal.strip()
                    neg = s.startswith('!')
                    name = s[1:] if neg else s
                    need(name in self.index, 'unknown literal: ' + name)
                    literals.append((self.index[name], 0 if neg else 1))
                terms.append(literals)
            self.terms.append(terms)
        self.w = json.loads((ROOT/'inputs/witnesses.json').read_text())
        need(self.names == self.w['nodes'], 'certificate bit order')
        self.env = self.w['environment']
        need(self.env == dict(DELTA=0, ECM=1, EGF=0, FAT4_L=1, HGF=0,
                             IL6=0, ROS=0, RPTP_L=1, TGFB=0, WNT=0), 'environment')
        self.E = self.w['xE']
        self.clamps = dict(ECad=0, PAK=0, FAK_SRC_b1=0, FAK_SRC_b2=0)
        self.chains = [('FAK_SRC_b1','FAK_SRC_b2'),('ECad_AJ_b1','ECad_AJ_b2'),
                       ('AJ_b1','AJ_b2'),('FA_b1','FA_b2','FA_b3')]
        self.readout = dict(AJ_b1=1, AJ_b2=1, FA_b1=0, FA_b2=0, FA_b3=0)
        self.candidates = set(self.names) - set(self.env) - set(self.clamps) - set(self.readout)
        need(len(self.candidates) == 37, '37 sensor bits')
        self.S = self.w['S']
        need(len(self.S) == len(set(self.S)) == 14 and set(self.S) <= self.candidates, 'sensor set')

    def bits(self, d):
        need(set(d) == set(self.names) and set(d.values()) <= {0,1}, 'full Boolean assignment')
        return sum(d[n] << i for i, n in enumerate(self.names))

    def match(self, s, d):
        return all(((s >> self.index[n]) & 1) == v for n,v in d.items())

    def overwrite(self, s, d):
        for n,v in d.items():
            i = self.index[n]
            s = (s & ~(1 << i)) | (v << i)
        return s

    def value(self, s, i):
        return int(any(all(((s >> v) & 1) == value for v, value in term)
                       for term in self.terms[i]))

    def update(self, s, n):
        i = self.index[n]
        return (s & ~(1 << i)) | (self.value(s, i) << i)

    def fixed(self, s):
        return all(self.value(s, i) == ((s >> i) & 1) for i in range(56))

    def safe(self, s):
        return self.match(s, {'AJ_b1':0, 'AJ_b2':0}) or self.match(s, {n:0 for n in self.readout if n.startswith('FA_')})

    def admissible(self, s):
        return all(((s >> self.index[a]) & 1) >= ((s >> self.index[b]) & 1)
                   for chain in self.chains for a,b in zip(chain,chain[1:]))

    def domain(self):
        b = self.b
        d = self.cube(self.env)
        for chain in self.chains:
            for low,high in zip(chain,chain[1:]):
                d = b.AND(d,b.OR(b.vars[self.index[low]],b.NOT(b.vars[self.index[high]])))
        return d

    def domain_checks(self):
        b = self.b
        d = self.domain()
        bad = b.NOT(d)
        for i in self.natural:
            need(b.AND(d,b.preimage(bad,i,self.f[i])) == 0, 'natural update leaves admissible domain')
        for phase in (0,1):
            image = d
            for n,v in (self.clamps | {'ECad':phase}).items():
                image = b.image(image,self.index[n],v)
            need(b.AND(image,bad) == 0, 'atomic corrected clamp leaves admissible domain')
        return {'domain_states':b.count(d),'natural_updates_checked':len(self.natural),
                'atomic_clamps_checked':2,'preserved':True}

    def symbolic(self):
        self.b = b = BDD(56)
        self.f = []
        for terms in self.terms:
            f = 0
            for term in terms:
                t = 1
                for v, value in term:
                    t = b.AND(t, b.vars[v] if value else b.NOT(b.vars[v]))
                f = b.OR(f,t)
            self.f.append(f)
        self.free = [i for i,n in enumerate(self.names) if n not in self.env and n not in self.clamps]
        self.natural = [i for i,n in enumerate(self.names) if n not in self.env]
        self.keep = []

    def collect(self, *roots):
        self.b.collect(self.f + self.keep + list(roots))

    def cube(self, d):
        return self.b.cube({self.index[n]:v for n,v in d.items()})

    def initial(self):
        b = self.b
        a = self.cube(self.env | dict(AJ_b1=0, AJ_b2=0, FA_b1=1, FA_b2=1, FA_b3=1))
        for i,f in enumerate(self.f):
            equal = b.OR(b.AND(b.vars[i],f), b.AND(b.NOT(b.vars[i]), b.NOT(f)))
            a = b.AND(a,equal)
        expected = 0
        for d in self.w['initial_models']:
            need(self.fixed(self.bits(d)) and self.match(self.bits(d), self.env), 'initial witness fixed')
            expected = b.OR(expected, self.cube(d))
        need(a == expected and b.count(a) == 2, 'complete M3 fixed-point set mismatch')
        need(b.AND(a,b.NOT(self.domain())) == 0,'initial points outside admissible domain')
        need(self.fixed(self.bits(self.E)) and self.match(self.bits(self.E),self.env | self.readout), 'reference E1')
        return a

    def lower(self):
        out, differences = [], []
        init = {self.bits(d) for d in self.w['initial_models']}
        for w in self.w['witnesses']:
            phase, state, released, violated = -1, None, False, False
            frames = w['trace']
            release_state = None
            for k,frame in enumerate(frames):
                target = int(frame['state'],16)
                need(0 <= target < 2**56, 'state range')
                need(self.admissible(target), 'trace outside admissible domain')
                kind = frame['kind']
                if k == 0:
                    need(kind == 'initial' and target in init and self.fixed(target), 'initial frame')
                    if 'initial_fixed_point' in w:
                        need(target == self.bits(w['initial_fixed_point']), 'witness initial assignment')
                    state = target
                    continue
                fa0 = self.match(state, dict(FA_b1=0, FA_b2=0, FA_b3=0))
                e1 = self.match(state,self.readout)
                if phase == -1:
                    need(kind == 'clamp' and frame['phase'] == 0, 'initial clamp is immediate')
                elif phase == 0 and fa0:
                    need(kind == 'clamp' and frame['phase'] == 1, 'first switch is immediate')
                elif phase == 1 and e1:
                    need(kind == 'release', 'first E1 releases immediately for missed difference set')
                if kind == 'clamp':
                    p = frame['phase']
                    need(p == phase+1 and p in (0,1), 'phase order')
                    need(p == 0 or fa0, 'phase1 gate')
                    want = self.overwrite(state,self.clamps | {'ECad':p})
                    phase = p
                elif kind == 'release':
                    need(phase == 1 and e1 and not released, 'release gate')
                    want = state
                    release_state = state
                    phase, released = 2, True
                elif kind == 'update':
                    n = frame['node']
                    need(n in self.index and n not in self.env, 'update node')
                    need(phase == 2 or n not in self.clamps, 'clamped node update forbidden')
                    want = self.update(state,n)
                else:
                    raise ValueError('unexpected trace kind')
                need(want == target, f'trace transition mismatch {w["label"]} frame {k}')
                need(self.match(target,self.env), 'trace environment')
                if phase < 2:
                    need(self.safe(target), 'pre-release safety witness')
                elif not self.safe(target) or not self.match(target,self.readout):
                    violated = True
                state = target
            need(released and violated, 'finite violation required')
            need(release_state == self.bits(w['release_state']), 'release assignment')
            D = {n for n in self.names if ((release_state >> self.index[n]) & 1) != self.E[n]}
            need(D == set(w['difference']) and D and D <= self.candidates, 'difference mismatch')
            need(all(D.isdisjoint(old) for old in differences), 'differences not pairwise disjoint')
            differences.append(D)
            out.append({'label':w['label'],'frames':len(frames),'difference':sorted(D),'finite_violation':True,'all_frames_admissible':True})
        need(len(out) == 14, '14 witnesses required')
        return out


def forward(net, seed, free, gate, label, log):
    b, reached = net.b, seed
    rounds = 0
    while True:
        before = reached
        # Gauss-Seidel closure: updates use the latest accumulated set.
        for i in free:
            allowed = b.AND(reached,b.NOT(gate))
            reached = b.OR(reached,b.image(allowed,i,net.f[i]))
        rounds += 1
        log(label, rounds=rounds, states=b.count(reached), nodes=len(b.nodes))
        if reached == before:
            break
        net.collect(reached,seed,gate)
    # Separate exact closure postcondition, independent of round stopping bookkeeping.
    for i in free:
        need(b.AND(b.image(b.AND(reached,b.NOT(gate)),i,net.f[i]),b.NOT(reached)) == 0, 'closure postcondition')
    return reached


def fair_avoid(net, domain, free, label, log):
    # Existence of an infinite path entirely in domain taking EACH label infinitely.
    # For each action i, retain states that can reach an i edge whose endpoint is
    # still in Z. Iterate this greatest fixed point. Self updates are included.
    b, Z, outer = net.b, domain, 0
    while True:
        old = Z
        for i in free:
            Y = b.AND(Z,b.preimage(Z,i,net.f[i]))
            while True:
                prev = Y
                for j in free:
                    Y = b.OR(Y,b.AND(Z,b.preimage(Y,j,net.f[j])))
                if Y == prev:
                    break
                net.collect(domain,Z,Y,old)
            Z = Y
            if Z == 0:
                break
        outer += 1
        log(label, rounds=outer, states=b.count(Z), nodes=len(b.nodes))
        if Z == old or Z == 0:
            return Z
        net.collect(domain,Z)


def upper(net, initial, log):
    b = net.b
    first = initial
    for n,v in net.clamps.items():
        first = b.image(first,net.index[n],v)
    fa0 = net.cube(dict(FA_b1=0,FA_b2=0,FA_b3=0))
    aj0 = net.cube(dict(AJ_b1=0,AJ_b2=0))
    safe = b.OR(fa0,aj0)
    gate = net.cube(net.readout | {n:net.E[n] for n in net.S})
    domain = net.domain()
    net.keep = [initial,first,fa0,aj0,safe,gate,domain]
    R0 = forward(net,first,net.free,fa0,'stage0_reach',log)
    net.keep.append(R0)
    need(b.AND(R0,b.NOT(safe)) == 0, 'stage0 unsafe')
    H0 = b.AND(R0,fa0)
    net.keep.append(H0)
    need(H0 != 0, 'stage0 gate unreachable')
    Z0 = fair_avoid(net,b.AND(R0,b.NOT(fa0)),net.free,'stage0_fair_avoid',log)
    need(Z0 == 0, 'fair stage0 guard avoidance possible')
    first1 = b.image(H0,net.index['ECad'],1)
    R1 = forward(net,first1,net.free,gate,'stage1_reach',log)
    net.keep.append(R1)
    need(b.AND(R1,b.NOT(safe)) == 0, 'stage1 unsafe')
    H1 = b.AND(R1,gate)
    net.keep.append(H1)
    need(H1 != 0,'stage1 gate unreachable')
    Z1 = fair_avoid(net,b.AND(R1,b.NOT(gate)),net.free,'stage1_fair_avoid',log)
    need(Z1 == 0, 'fair stage1 guard avoidance possible')
    R2 = forward(net,H1,net.natural,0,'released_reach',log)
    need(b.AND(R2,b.NOT(net.cube(net.readout))) == 0, 'released E1 violation')
    for phase,R in enumerate((R0,R1,R2)):
        need(b.AND(R,b.NOT(domain)) == 0,f'phase{phase} reachable inadmissible state')
    return {'stage0_states':b.count(R0),'stage0_gate_states':b.count(H0),
            'stage1_states':b.count(R1),'stage1_gate_states':b.count(H1),
            'released_states':b.count(R2),'fair_avoid_stage0':0,'fair_avoid_stage1':0,
            'all_prefix_safe':True,'released_E1_invariant':True,'all_reachable_admissible':True,'S':net.S}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode',choices=['basic','upper'],required=True)
    ap.add_argument('--output',required=True)
    args = ap.parse_args()
    start, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('580 second limit')))
    signal.alarm(580)
    output = ROOT/args.output
    need(not output.exists(),'refuse to overwrite a trial')
    events = []
    def log(label,**kw):
        row = {'label':label,'seconds':round(time.monotonic()-start,6),**kw}
        events.append(row)
        print(json.dumps(row),flush=True)
        need(rss_bytes() < 2*1024**3, 'RSS cap')
    result = {'mode':args.mode,'events':events,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'python':sys.version,'platform':platform.platform(),'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        if args.mode == 'basic':
            result['kernel'] = kernel_test()
        net = Network()
        net.symbolic()
        result['domain'] = net.domain_checks()
        initial = net.initial()
        result['initial_fixed_points'] = net.b.count(initial)
        log('initial',count=net.b.count(initial),nodes=len(net.b.nodes))
        if args.mode == 'basic':
            result['lower'] = net.lower()
        else:
            result['upper'] = upper(net,initial,log)
        result['status'] = 'PASS'
    except Exception as e:
        result['status'] = 'INCOMPLETE' if isinstance(e,TimeoutError) or 'budget' in str(e) or 'cap' in str(e) else 'FAIL'
        result['error'] = repr(e)
    finally:
        result.update(wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
                      peak_rss_bytes=rss_bytes(),processes=1,cost_usd=0)
        output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('events','lower')}),flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
