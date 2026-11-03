#!/usr/bin/env python3
"""Exhaustive 108-family classification using only the reviewer's ROBDD.
The original check did not read the producer uniqueness-extension code, proof, or results.
"""
import argparse,hashlib,itertools,json,math,platform,signal,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bdd_check as own

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output)
    own.need(not out.exists(),'refuse receipt overwrite');start=time.monotonic();cpu=time.process_time();events=[]
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('580 second limit')));signal.alarm(580)
    result={'status':'RUNNING','next15_code_or_proof_or_result_read':False,'additional_agent_used':False,
            'python':sys.version,'platform':platform.platform(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    def log(label,**kw):
        events.append({'label':label,'seconds':time.monotonic()-start,**kw});print(json.dumps(events[-1]),flush=True)
        own.need(own.rss_bytes()<2*1024**3,'RSS cap')
    try:
        net=own.Network();net.symbolic();b=net.b;initial=net.initial();result['domain']=net.domain_checks()
        lower=net.lower();result['replayed_lower_witnesses']=lower
        groups=[r['difference'] for r in lower];combos=[tuple(sorted(c)) for c in itertools.product(*groups)]
        own.need(len(combos)==len(set(combos))==math.prod(map(len,groups))==108,'complete 108-family')
        own.need(all(len(set(c))==14 for c in combos),'family sets contain 14 bits')
        original_S=sorted(net.S);result['original_S']=original_S
        first=initial
        for n,v in net.clamps.items():first=b.image(first,net.index[n],v)
        fa0=net.cube(dict(FA_b1=0,FA_b2=0,FA_b3=0));readout=net.cube(net.readout);domain=net.domain()
        net.keep=[initial,first,fa0,readout,domain]
        r0=own.forward(net,first,net.free,fa0,'phase0',log);net.keep.append(r0)
        h0=b.AND(r0,fa0);net.keep.append(h0);first1=b.image(h0,net.index['ECad'],1);net.keep.append(first1)
        all1=own.forward(net,first1,net.free,0,'unreleased_phase1',log);net.keep.append(all1)
        e1=b.AND(all1,readout);net.keep.append(e1)
        first_reach=own.forward(net,first1,net.free,readout,'first_E1_phase1',log);net.keep.append(first_reach)
        first_e1=b.AND(first_reach,readout);net.keep.append(first_e1)
        own.need(b.AND(all1,b.NOT(domain))==0,'unreleased states admissible')
        # Maximal universal E1 invariant of the fully released network.
        kernel=b.AND(domain,readout);net.keep.append(kernel);kernel_counts=[]
        while True:
            before=kernel
            for i in net.natural:kernel=b.AND(kernel,b.preimage(kernel,i,net.f[i]))
            kernel_counts.append(b.count(kernel));log('released_E1_kernel',rounds=len(kernel_counts),states=b.count(kernel))
            if kernel==before:break
            net.collect(kernel)
        net.keep.append(kernel)
        for i in net.natural:own.need(b.AND(kernel,b.NOT(b.preimage(kernel,i,net.f[i])))==0,'kernel closure')
        result['common_sets']={'phase0_states':b.count(r0),'phase0_gate':b.count(h0),'unreleased_phase1':b.count(all1),
                               'all_E1':b.count(e1),'first_E1':b.count(first_e1),'first_E1_equals_all_E1':first_e1==e1,
                               'released_E1_kernel':b.count(kernel),'kernel_iteration_counts':kernel_counts}
        rows=[];survivors=[]
        for c in combos:
            guard=net.cube({n:net.E[n] for n in c});all_gate=b.AND(e1,guard);first_gate=b.AND(first_e1,guard)
            bad=b.AND(first_gate,b.NOT(kernel))
            row={'S':list(c),'all_E1_guard_states':b.count(all_gate),'first_E1_guard_states':b.count(first_gate),
                 'bad_first_E1_release_states':b.count(bad),'classification':'finite_E1_violation_after_first_E1_release' if bad else 'pending_full_check'}
            rows.append(row)
            if not bad:survivors.append(row)
        result['classification']=rows
        log('safety_classification',family=len(rows),unsafe=sum(bool(r['bad_first_E1_release_states']) for r in rows),survivors=len(survivors))
        # Failures before this point still preserve the complete classification.
        own.need(len(survivors)<=10,'too many survivors for bounded final trial')
        full=[];result['full_candidate_checks']=full
        for row in survivors:
            net.S=row['S'];log('candidate_full_check',S=net.S)
            try:
                proof=own.upper(net,initial,log)
                row['classification']='valid_optimal_14_set';full.append({'S':net.S,'status':'PASS','all_path_result':proof})
            except ValueError as e:
                # Do not call an implementation error a disproved scientific claim.
                full.append({'S':net.S,'status':'UNRESOLVED','error':repr(e)});raise
        valid=[r['S'] for r in full if r['status']=='PASS'];result['valid_optimal_sets']=valid
        own.need(all(r['classification']!='pending_full_check' for r in rows),'complete classification required')
        own.need(original_S in valid,'previous successful set failed')
        deletion=[]
        for S in valid:
            for n in S:
                hits=[r for r in lower if set(r['difference'])&set(S)=={n}]
                own.need(len(hits)==1,'each chosen bit must be sole hit of one lower group')
                deletion.append({'S':S,'removed_bit':n,'violating_witness':hits[0]['label'],'missed_difference':hits[0]['difference']})
        result['deletion_certificates']=deletion
        result['verdict']={'unique_optimal_14_set':len(valid)==1,'optimal_14_set_count':len(valid),
                           'every_bit_essential_within_each_reported_set':True,
                           'all_original_bits_in_every_optimal_14_set':all(set(original_S)<=set(S) for S in valid),
                           'common_bits_of_optimal_sets':sorted(set.intersection(*(set(S) for S in valid))),
                           'all_108_guards_reachable':all(r['all_E1_guard_states']>0 for r in rows),
                           'scope':'specified Boolean current-value equality guards, fixed inputs and four-bit intervention; no general-guard or native-multivalued claim'}
        result['status']='PASS'
    except Exception as e:
        result['status']='INCOMPLETE' if isinstance(e,TimeoutError) or 'budget' in str(e) or 'cap' in str(e) else 'ERROR'
        result['error']=repr(e)
    result.update(events=events,wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
                  peak_rss_bytes=own.rss_bytes(),processes=1,cost_usd=0,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'verdict':result.get('verdict'),'error':result.get('error')}))
    return 0 if result['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
