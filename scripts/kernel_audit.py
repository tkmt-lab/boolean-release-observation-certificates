#!/usr/bin/env python3
"""Audit our checker against small explicit graphs and damaged certificates."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import resource
import signal
import sys
import time
from types import SimpleNamespace
import argparse

sys.path.insert(0,str(Path(__file__).resolve().parent))
from bdd_check import BDD, Network, ROOT, fair_avoid, need, rss_bytes


def explicit_fair(domain, formulas):
    edges = {s: [(s & ~(1 << i)) | (((f >> s) & 1) << i)
                 for i,f in enumerate(formulas)] for s in domain}
    reach = {s:{s} | (set(edges[s]) & domain) for s in domain}
    for k in domain:
        for s in domain:
            if k in reach[s]:
                reach[s] |= reach[k]
    components = {frozenset(t for t in domain if t in reach[s] and s in reach[t]) for s in domain}
    good = set()
    for C in components:
        if all(any(edges[s][i] in C for s in C) for i in range(len(formulas))):
            good |= C
    return {s for s in domain if reach[s] & good}


def audit_fairness():
    # Covers stable self loops, oscillations, multiple SCCs, transient paths,
    # and action-starvation cycles. Exhaust all 256 domains in each network.
    models = [(170,204,240),(85,51,15),(204,240,170),(150,105,232),
              (0,255,170),(128,254,23),(232,23,150),(240,51,105)]
    positive = negative = 0
    for formulas in models:
        b = BDD(3)
        def subset(states):
            r = 0
            for s in states:
                r = b.OR(r,b.cube({i:(s >> i)&1 for i in range(3)}))
            return r
        fs = [subset(s for s in range(8) if (f >> s)&1) for f in formulas]
        net = SimpleNamespace(b=b,f=fs,collect=lambda *r:b.collect(fs+list(r)))
        for mask in range(256):
            domain = {s for s in range(8) if (mask >> s)&1}
            a = subset(domain)
            got = fair_avoid(net,a,list(range(3)),'audit',lambda *a,**kw:None)
            got_set = {s for s in range(8) if b.contains(got,s)}
            expected = explicit_fair(domain,formulas)
            need(got_set == expected, f'fairness discrepancy {formulas} {mask}')
            positive += bool(expected)
            negative += not bool(expected)
            b.collect(fs)
    return {'explicit_SCC_comparisons':len(models)*256,'nonempty_fair_sets':positive,'empty_fair_sets':negative}


def audit_formulas(net):
    count = 0
    for i,terms in enumerate(net.terms):
        support = sorted({v for t in terms for v,_ in t})
        for bits in itertools.product((0,1),repeat=len(support)):
            state = sum(x << v for v,x in zip(support,bits))
            need(net.value(state,i) == net.b.contains(net.f[i],state),'DNF/BDD truth-table mismatch')
            count += 1
    return {'rules':56,'local_truth_table_rows':count}


def audit_mutations(net):
    saved = copy.deepcopy(net.w)
    cases = []
    def reject(label,edit,action):
        net.w = copy.deepcopy(saved)
        edit(net.w)
        try:
            action()
        except ValueError as e:
            cases.append({'mutation':label,'rejected':True,'reason':str(e)})
        else:
            raise ValueError('bad certificate accepted: '+label)
    reject('wrong_initial',lambda w:w['witnesses'][0]['trace'][0].update(state='00000000000000'),net.lower)
    reject('wrong_update_bit',lambda w:w['witnesses'][0]['trace'][2].update(state='00000000000000'),net.lower)
    reject('omit_immediate_phase_switch',lambda w:w['witnesses'][0]['trace'].pop(5),net.lower)
    reject('incorrect_release_assignment',lambda w:w['witnesses'][0]['release_state'].update(PI3K=0),net.lower)
    reject('missing_difference',lambda w:w['witnesses'][0]['difference'].pop(),net.lower)
    reject('overlapping_witness_differences',lambda w:w['witnesses'].__setitem__(1,copy.deepcopy(w['witnesses'][0])),net.lower)
    reject('omit_one_initial_model',lambda w:w['initial_models'].pop(),net.initial)
    prior = json.loads((ROOT/'inputs/prior-witnesses.json').read_text())
    reject('unchanged_legacy_witnesses',lambda w:w.update(witnesses=prior['witnesses']),net.lower)
    net.w = saved
    keep = dict(net.clamps)
    del net.clamps['FAK_SRC_b2']
    try:
        net.domain_checks()
    except ValueError as e:
        cases.append({'mutation':'omit_FAK_SRC_b2_clamp','rejected':True,'reason':str(e)})
    else:
        raise ValueError('missing b2 clamp not rejected')
    finally:
        net.clamps = keep
    return cases


def compare_prior(net):
    prior = json.loads((ROOT/'inputs/prior-witnesses.json').read_text())
    old = {w['label']:w for w in prior['witnesses']}
    rows = []
    for w in net.w['witnesses']:
        before = old[w['label']]
        converted,removed,phase,state = [],0,-1,None
        changed_states = 0
        for f in before['trace']:
            kind = f['kind']
            if kind == 'initial':
                state = int(f['state'],16)
            elif kind == 'clamp':
                phase = f['phase']
                state = net.overwrite(state,net.clamps | {'ECad':phase})
            elif kind == 'release':
                phase = 2
            elif kind == 'update':
                if phase in (0,1) and f['node'] == 'FAK_SRC_b2':
                    removed += 1
                    continue
                state = net.update(state,f['node'])
            else:
                raise ValueError('unexpected old action')
            changed_states += int(f['state'],16) != state
            converted.append(f | {'state':format(state,'014x')})
        need(converted == w['trace'], 'revised path is not reproduced by revised clamp/removing b2 updates')
        need(before['difference'] == w['difference'],'difference group changed')
        need(before['release_state'] == w['release_state'],'release state changed')
        rows.append({'label':w['label'],'trace_changed':before['trace'] != w['trace'],
                     'old_frames':len(before['trace']),'new_frames':len(w['trace']),
                     'removed_controlled_b2_updates':removed,'remaining_frames_with_changed_state':changed_states,
                     'old_inadmissible_frames':sum(not net.admissible(int(f['state'],16)) for f in before['trace']),
                     'new_inadmissible_frames':sum(not net.admissible(int(f['state'],16)) for f in w['trace']),
                     'same_difference':True,'same_release_state':True,'transformed_path_matches':True})
    return {'same_S':net.S == prior['S'],'same_initial_models':net.w['initial_models']==prior['initial_models'],
            'rows':rows,'changed_labels':[r['label'] for r in rows if r['trace_changed']]}


def main():
    start = time.monotonic()
    cpu = time.process_time()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('580 second limit')))
    signal.alarm(580)
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    need(not out.exists(),'output collision')
    result = {'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'checker_sha256':hashlib.sha256((ROOT/'scripts/bdd_check.py').read_bytes()).hexdigest(),
              'audit_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        result['fairness'] = audit_fairness()
        net = Network()
        net.symbolic()
        result['formulas'] = audit_formulas(net)
        result['negative_controls'] = audit_mutations(net)
        result['previous_comparison'] = compare_prior(net)
        result['status'] = 'PASS'
    except Exception as e:
        result['status'],result['error'] = 'FAIL',repr(e)
    finally:
        result.update(wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
                      peak_rss_bytes=rss_bytes(),processes=1,cost_usd=0)
        out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
