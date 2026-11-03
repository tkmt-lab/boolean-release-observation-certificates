"""Standalone certificate consumer: no imports of the producer/model/SAT modules."""
import ast,copy,hashlib,itertools,json,resource,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent

def main():
    if not __debug__: raise SystemExit('Assertions must be enabled; do not use -O')
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    clock=time.monotonic(); resource.setrlimit(resource.RLIMIT_CPU,(590,600))
    old=HERE/'inputs'; raw=(old/'biomodels-derived.bnet').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='e15ee45915ca1ff81b363cdf24db1a4f4fab37f250e6b3e57cf8ff9ca52d744d'
    syntax={}; dnf={}
    for line in raw.decode().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line.startswith('targets,'): continue
        n,expr=map(str.strip,line.split(',',1))
        syntax[n]=ast.parse(expr.replace('!',' not ').replace('&',' and ').replace('|',' or ').strip(),mode='eval')
        dnf[n]=[[(w.strip()[1:],False) if w.strip().startswith('!') else (w.strip(),True) for w in t.split('&')] for t in expr.split('|')]
    names=list(syntax); index={n:i+1 for i,n in enumerate(names)}
    groups=[['FAK_SRC_b1','FAK_SRC_b2'],['ECad_AJ_b1','ECad_AJ_b2'],['AJ_b1','AJ_b2'],['FA_b1','FA_b2','FA_b3']]
    def admissible(s): return all(s[a]>=s[b] for bs in groups for a,b in zip(bs,bs[1:]))
    def ev(t,s):
        if isinstance(t,ast.Expression): return ev(t.body,s)
        if isinstance(t,ast.Name): return bool(s[t.id])
        if isinstance(t,ast.UnaryOp): assert isinstance(t.op,ast.Not); return not ev(t.operand,s)
        assert isinstance(t,ast.BoolOp)
        if isinstance(t.op,ast.And): return all(ev(x,s) for x in t.values)
        assert isinstance(t.op,ast.Or); return any(ev(x,s) for x in t.values)
    def f(n,s): return int(ev(syntax[n],s))
    def decode(bits): return {n:(int(bits,16)>>i)&1 for i,n in enumerate(names)}
    domain_cases=0
    for bits in groups:
        for n in bits:
            support={a.id for a in ast.walk(syntax[n]) if isinstance(a,ast.Name)}|set(bits)
            touched=[bs for bs in groups if support&set(bs)]
            support=sorted(support|{b for bs in touched for b in bs})
            for vals in itertools.product(range(2),repeat=len(support)):
                s=dict(zip(support,vals))
                if any(s[a]<s[b] for bs in touched for a,b in zip(bs,bs[1:])): continue
                t={**s,n:f(n,s)}
                assert all(t[a]>=t[b] for bs in touched for a,b in zip(bs,bs[1:]))
                domain_cases+=1
    assert domain_cases==324
    projection_count=0
    for n in names:
        support={a.id for a in ast.walk(syntax[n]) if isinstance(a,ast.Name)}
        if 'FAK_SRC_b2' not in support and n!='FAK_SRC_b2': continue
        rest=sorted(support-{'FAK_SRC_b1','FAK_SRC_b2'})
        for vals in itertools.product(range(2),repeat=len(rest)):
            s={**dict(zip(rest,vals)),'FAK_SRC_b1':0,'FAK_SRC_b2':0}
            assert f(n,s)==f(n,{**s,'FAK_SRC_b2':1})
            if n=='FAK_SRC_b2': assert f(n,s)==0
        projection_count+=1
    assert projection_count==4

    inputs={'DELTA':0,'ECM':1,'EGF':0,'FAT4_L':1,'HGF':0,'IL6':0,'ROS':0,'RPTP_L':1,'TGFB':0,'WNT':0}
    readout=['AJ_b1','AJ_b2','FA_b1','FA_b2','FA_b3']; controls=[{'ECad':0,'PAK':0,'FAK_SRC_b1':0,'FAK_SRC_b2':0},{'ECad':1,'PAK':0,'FAK_SRC_b1':0,'FAK_SRC_b2':0}]
    target=json.loads((old/'witnesses.json').read_text())['xE']
    assert all(f(n,target)==target[n] for n in names) and admissible(target)
    def e1(s): return [s[n] for n in readout]==[1,1,0,0,0]
    def safe(s): return [s[n] for n in readout[:2]]==[0,0] or [s[n] for n in readout[2:]]==[0,0,0]
    proof_nodes=0; propagated_units=0
    def proof_check(cnf,tree):
        def go(node,known):
            nonlocal proof_nodes,propagated_units
            proof_nodes+=1; known=set(known)
            for step in node['units']:
                c=cnf[step['reason']]; assert not any(l in known for l in c)
                unset=[l for l in c if -l not in known and l not in known]
                assert unset==[step['literal']]; known.add(step['literal']); propagated_units+=1
            if 'conflict' in node:
                assert all(-l in known for l in cnf[node['conflict']]); return
            v=node['split']; assert v>0 and v not in known and -v not in known
            go(node['false'],known|{-v}); go(node['true'],known|{v})
        go(tree,set())
    def canonical(cnf): return sorted({tuple(sorted(set(c))) for c in cnf})
    def bind(y,terms,fresh):
        out=[]; choices=[]
        for term in terms:
            if len(term)>1:
                t=fresh; fresh+=1
                out.extend([[-t,a] for a in term]); out.append([t]+[-a for a in term]); choices.append(t)
            else: choices.append(term[0])
        out.append([-y]+choices)
        out.extend([[y,-t] for t in choices])
        return out,fresh
    terms=lambda n:[[(index[v] if sign else -index[v]) for v,sign in t] for t in dnf[n]]
    lit=lambda n,v:index[n] if v else -index[n]
    initial=json.loads((HERE/'certificates'/'initial-fixed-points.json').read_text()); assert initial['nodes']==names
    # Decode the saved Tseitin conjunctions in their certificate ordering.
    # Their formulas are NOT accepted as model input: each is exhaustively
    # checked against the independently SBML-derived Boolean rule below.
    cursor=0; fresh=57; auxiliaries={}; saved_terms={}
    for n in names:
        y=index[n]
        if n in inputs:
            assert initial['cnf'][cursor:cursor+2]==[[-y,y],[-y,y]]
            saved_terms[n]=[[(n,True)]]; cursor+=2; continue
        while initial['cnf'][cursor][0]==-fresh:
            literals=[]
            while initial['cnf'][cursor][0]==-fresh:
                c=initial['cnf'][cursor]
                assert len(c)==2 and 1<=abs(c[1])<=56
                literals.append(c[1]); cursor+=1
            assert len(literals)>1
            assert initial['cnf'][cursor]==[fresh]+[-v for v in literals]
            auxiliaries[fresh]=literals;fresh+=1;cursor+=1
        while initial['cnf'][cursor][0]!=-y:
            c=initial['cnf'][cursor];assert len(c)==2 and y in c;cursor+=1
        choices=initial['cnf'][cursor][1:];cursor+=1
        assert choices
        numeric=[]
        for v in choices:
            if abs(v)<=56:numeric.append([v])
            else:assert v in auxiliaries;numeric.append(auxiliaries[v])
        saved_terms[n]=[[(names[abs(v)-1],v>0) for v in t] for t in numeric]
    encoding_cases=0
    for n in names:
        ss=sorted({a.id for a in ast.walk(syntax[n]) if isinstance(a,ast.Name)} |
                  {v for term in saved_terms[n] for v,_ in term})
        for vals in itertools.product((0,1),repeat=len(ss)):
            s=dict(zip(ss,vals))
            recovered=any(all(bool(s[v])==sign for v,sign in term) for term in saved_terms[n])
            assert recovered==bool(f(n,s));encoding_cases+=1
    dnf=saved_terms
    expected=[]; fresh=57
    for n in names:
        rows,fresh=bind(index[n],terms(n),fresh); expected+=rows
    expected += [[lit(n,v)] for n,v in {**inputs,**dict(zip(readout,[0,0,1,1,1]))}.items()]
    assert canonical(expected)==canonical(initial['cnf'])
    assert len(initial['models'])==initial['count']==2
    for s in initial['models']:
        assert [s[n] for n in readout]==[0,0,1,1,1] and admissible(s)
        assert all(s[n]==v for n,v in inputs.items()) and all(f(n,s)==s[n] for n in names)
    blocking=[[-lit(n,s[n]) for n in names] for s in initial['models']]
    assert blocking==initial['blocking']
    proof_check(initial['cnf']+blocking,initial['final_unsat_proof'])
    lower=json.loads((HERE/'certificates'/'lower-result.json').read_text())
    def trace_check(w):
        frames=w['trace']; s=decode(frames[0]['state']); assert s in initial['models']
        assert frames[0]["kind"]=="initial"
        phase=-1; actual_release=None
        for i,row in enumerate(frames[1:],1):
            expected=dict(s)
            fa0=[s[n] for n in readout[2:]]==[0,0,0]
            if phase==-1: assert row['kind']=='clamp' and row['phase']==0
            if phase==0 and fa0: assert row['kind']=='clamp' and row['phase']==1
            if phase==1 and e1(s): assert row['kind']=='release'
            if row['kind']=='clamp':
                assert row['phase']==phase+1 and phase<1
                if row['phase']==1: assert fa0
                phase+=1; expected.update(controls[phase])
            elif row['kind']=='release':
                assert phase==1 and e1(s); actual_release=dict(s); phase=2
            else:
                assert row['kind']=='update'
                n=row['node']; assert n not in inputs and (phase==2 or n not in controls[phase]); expected[n]=f(n,s)
            s=decode(row['state']); assert s==expected and admissible(s) and all(s[n]==v for n,v in inputs.items())
            if phase<2: assert safe(s)
            if phase==0 and [s[n] for n in readout[2:]]==[0,0,0]: assert frames[i+1]['kind']=='clamp'
            if phase==1 and e1(s): assert frames[i+1]['kind']=='release'
        assert phase==2 and (not e1(s) or not safe(s))
        assert actual_release is not None and w['release_state']==actual_release
        D={n for n in names if w['release_state'][n]!=target[n]}
        assert D==set(w['difference']) and D and D<=set(names)-set(inputs)-set(controls[1])-set(readout)
        return D
    differences=[trace_check(w) for w in lower['witnesses']]
    assert len(differences)==14 and all(not a&b for a,b in itertools.combinations(differences,2))
    cert=json.loads((HERE/'certificates'/'upper-result.json').read_text()); I0,I1=cert['I0'],cert['I1']; S=cert['S']
    assert len(set(S))==len(S)==14 and set(S)<=set(names)-set(inputs)-set(controls[1])-set(readout)
    assert all(any(n in D for n in S) for D in differences)
    assert all(0<abs(l)<=56 for c in I0+I1 for l in c)
    assert all(index['ECad'] not in {abs(l) for l in c} for c in I0+I1)
    for m in initial['models']:
        s={**m,**controls[0]}; assert all(any(bool(s[names[abs(l)-1]])==(l>0) for l in c) for c in I0)
    queries={q['label']:q for q in cert['queries']}; used=set()
    def query(label,expected):
        q=queries[label]; assert q['status']=='UNSAT' and canonical(q['cnf'])==canonical(expected)
        proof_check(q['cnf'],q['proof']); used.add(label)
    for mode,I in enumerate([I0,I1]):
        root=I+[[lit(n,v)] for n,v in {**inputs,**controls[mode]}.items()]
        for n in names:
            if n in inputs or n in controls[mode]: continue
            eq,_=bind(57,terms(n),58)
            for j,c in enumerate(I):
                signs=[l for l in c if abs(l)==index[n]]
                if not signs: continue
                assert len(signs)==1
                extra=[[-l] for l in c if abs(l)!=index[n]]+[[-57 if signs[0]>0 else 57]]
                query(f'I{mode}/update/{n}/clause/{j}',root+eq+extra)
    for j,c in enumerate(I1): query(f'switch/clause/{j}',I0+[[-l] for l in c])
    guard={**inputs,**controls[1],**{n:target[n] for n in readout+S}}; pins=cert['post_cube']['pins']
    assert set(guard)<=set(pins) and all(pins[n]==v for n,v in guard.items())
    for n,v in pins.items():
        assert n in names and v==target[n]
        if n not in guard: query(f'guard-implies/{n}/{v}',I1+[[lit(k,w)] for k,w in guard.items()]+[[-lit(n,v)]])
    assert used==set(queries) and len(used)==70 and not cert['failed_queries']
    unknown=sorted(set(names)-set(pins)); states=0
    for vals in itertools.product(range(2),repeat=len(unknown)):
        s={**pins,**dict(zip(unknown,vals))}; assert e1(s) and admissible(s)
        assert all(f(n,s)==v for n,v in pins.items() if n not in inputs); states+=1
    assert states==1024
    def constant(n,partial,v):
        support=sorted({node.id for node in ast.walk(syntax[n]) if isinstance(node,ast.Name)}-set(partial))
        for vals in itertools.product(range(2),repeat=len(support)): assert f(n,{**partial,**dict(zip(support,vals))})==v
    live=json.loads((HERE/'certificates'/'liveness.json').read_text()); current={**inputs,**controls[1]}
    def layers(rows):
        for layer in rows:
            for row in layer:
                assert row['value']==target[row['node']]
                if row['node'] in current:
                    assert row['node']=='FAK_SRC_b2' and current[row['node']]==row['value']
                else: constant(row['node'],current,row['value'])
            current.update({row['node']:row['value'] for row in layer})
    layers(live['layers_before_core']); core=live['core']; ranks={tuple(r['state']):r['rank'] for r in core['rank']}
    assert set(ranks)==set(itertools.product([0,1],repeat=2)) and len(set(ranks.values()))==4
    for pair in itertools.product([0,1],repeat=2):
        rows=[r for r in core['table'] if r['state']==list(pair)]; assert {r['node'] for r in rows}=={'p120_AJ','RAP1'}
        for r in rows:
            partial={**current,**dict(zip(['p120_AJ','RAP1'],pair))}; constant(r['node'],partial,r['value'])
            nxt=list(pair); nxt[['p120_AJ','RAP1'].index(r['node'])]=r['value']; assert nxt==r['next'] and ranks[tuple(nxt)]<=ranks[pair]
        if pair!=(1,0): assert any(r['next']!=list(pair) for r in rows)
    current.update({'p120_AJ':1,'RAP1':0}); layers(live['layers_after_core']); assert current==target
    p0={**inputs,**controls[0],'AJ_b1':0,'AJ_b2':0}
    for n in ['AJ_b1','AJ_b2']: constant(n,p0,0)
    for n in ['FA_b3','FA_b2','FA_b1']: constant(n,p0,0); p0[n]=0
    for n in ['FA_b1','FA_b2','FA_b3']: constant(n,{**inputs,**controls[1],'FA_b1':0,'FA_b2':0,'FA_b3':0},0)
    bad=copy.deepcopy(lower['witnesses'][-1]); bad['trace'][2]['state']=format(int(bad['trace'][2]['state'],16)^1,'014x')
    try: trace_check(bad)
    except AssertionError: corruption=True
    else: raise AssertionError('Corrupt trace accepted')
    u=resource.getrusage(resource.RUSAGE_SELF)
    result={'status':'PASS','claimed_minimum':14,'lower_disjoint_groups':14,'upper_S':S,'initial_fixed_points':2,
            'initial_complete_enumeration_proof':True,'cnf_to_model_local_cases':encoding_cases,'inductiveness_queries':len(used),'proof_tree_nodes':proof_nodes,'unit_steps_checked':propagated_units,
            'post_cube_states_checked':states,'global_fair_convergence_nodes':len(current),'admissibility_local_cases':domain_cases,'controlled_projection_functions':projection_count,'candidate_observation_bits':37,'corrupted_trace_rejected':corruption,
            'checker_imports_producer_modules':False,'same_process_generation_preceded_checker':False,'independent_agent_review':False,'Lean':False,
            'wall_seconds':time.monotonic()-clock,'cpu_seconds':u.ru_utime+u.ru_stime,
            'peak_rss_bytes':u.ru_maxrss*(1 if sys.platform=='darwin' else 1024),'processes':1,'cost_usd':0,
            'scope':'Saved certificates only; no generation. Four-bit atomic clamp, 37 candidate bits. See VERIFICATION-RECORD.md for separate-reviewer and proof-exposure limits; no Lean or native-51-species fairness/optimality claim.'}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
