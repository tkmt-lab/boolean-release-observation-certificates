#!/usr/bin/env python3
"""CC0 SBML-qual -> unit-step threshold Boolean rules, using only stdlib.

Decode a threshold word by its longest prefix of ones. For output threshold i,
use (target >= i and current prefix >= i-1) or current prefix >= i+1.
This defines every Boolean word, including inadmissible threshold words.
"""
import argparse,ast,hashlib,itertools,json,time,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
Q='{http://www.sbml.org/sbml/level3/version1/qual/version1}'
M='{http://www.w3.org/1998/Math/MathML}'
SOURCE_SHA='0be06df8664e0f6e187298753703110063d533384b14f22cabd4b569af06dd65'
def need(ok,msg):
    if not ok: raise ValueError(msg)
def sha(b): return hashlib.sha256(b).hexdigest()
def load(path):
    raw=path.read_bytes();need(sha(raw)==SOURCE_SHA,'SBML source hash mismatch')
    r=ET.fromstring(raw)
    species={e.get(Q+'id'):(int(e.get(Q+'maxLevel')),e.get(Q+'constant')=='true') for e in r.iter(Q+'qualitativeSpecies')}
    need(len(species)==51,'51 unique qualitative species required')
    rules={}
    for e in r.iter(Q+'transition'):
        outputs=list(e.iter(Q+'output'));need(len(outputs)==1,'single output required')
        out=outputs[0];n=out.get(Q+'qualitativeSpecies')
        need(n in species and not species[n][1] and n not in rules and out.get(Q+'transitionEffect')=='assignmentLevel','transition output')
        default=list(e.iter(Q+'defaultTerm'));need(len(default)==1 and default[0].get(Q+'resultLevel')=='0','default level must be zero')
        terms=[]
        for t in e.iter(Q+'functionTerm'):
            level=int(t.get(Q+'resultLevel'));need(0<level<=species[n][0],'result level')
            def parse(x):
                tag=x.tag.removeprefix(M);cs=list(x)
                if tag=='math': need(len(cs)==1,'math arity');return parse(cs[0])
                need(tag=='apply' and len(cs)>=2,'MathML apply expected')
                op=cs[0].tag.removeprefix(M)
                if op in ('and','or'):return (op,tuple(parse(c) for c in cs[1:]))
                need(op in ('eq','geq','leq') and len(cs)==3 and cs[1].tag==M+'ci' and cs[2].tag==M+'cn','unsupported MathML')
                v=cs[1].text.strip();k=int(cs[2].text);need(v in species and 0<=k<=species[v][0],'comparison range')
                return (op,v,k)
            terms.append((level,parse(t.find(M+'math'))))
        rules[n]=terms
    need(len(rules)==41 and set(rules)=={n for n,(_,c) in species.items() if not c},'41 transitions required')
    return species,rules

def refs(t):
    return set().union(*(refs(c) for c in t[1])) if t[0] in ('and','or') else {t[1]}
def math_eval(t,s):
    op=t[0]
    if op=='and':return all(math_eval(c,s) for c in t[1])
    if op=='or':return any(math_eval(c,s) for c in t[1])
    v,k=s[t[1]],t[2]
    return v==k if op=='eq' else v>=k if op=='geq' else v<=k

def bitnames(n,m):return [n] if m==1 else [n+'_b'+str(i) for i in range(1,m+1)]
def decode(n,m,s):
    k=0
    for b in bitnames(n,m):
        if not s[b]:break
        k+=1
    return k

def primes(support,truth):
    # Quine-McCluskey: retain all prime implicants, no don't-care assignments.
    active={(i,0) for i,v in enumerate(truth) if v};done=set();width=len(support)
    while active:
        used=set();nxt=set()
        for value,mask in active:
            for j in range(width):
                bit=1<<j
                if not (mask|value)&bit and (value|bit,mask) in active:
                    used.update(((value,mask),(value|bit,mask)));nxt.add((value,mask|bit))
        done.update(active-used);active=nxt
    terms=[]
    for value,mask in sorted(done):
        lits=[]
        for j,n in enumerate(support):
            bit=1<<(width-1-j)
            if not mask&bit:lits.append(n if value&bit else '!'+n)
        need(lits,'constant true unsupported for this pinned model');terms.append('&'.join(lits))
    need(terms,'constant false unsupported for this pinned model')
    return ' | '.join(sorted(terms))

def generate(source):
    species,rules=load(source);rows={};checks=0;admissible_cases=0
    for n,(m,const) in species.items():
        deps={n} if const else set().union(*(refs(t) for _,t in rules[n]))
        if m>1:deps.add(n)
        support=sorted(b for v in deps for b in bitnames(v,species[v][0]))
        tables=[[] for _ in range(m)]
        for vals in itertools.product((0,1),repeat=len(support)):
            s=dict(zip(support,vals));levels={v:decode(v,species[v][0],s) for v in deps}
            active=[level for level,t in rules.get(n,[]) if math_eval(t,levels)]
            need(len(active)<=1,'overlapping SBML function terms')
            target=levels[n] if const else (active[0] if active else 0)
            valid=all(all(s[a]>=s[b] for a,b in zip(bitnames(v,species[v][0]),bitnames(v,species[v][0])[1:])) for v in deps)
            for i in range(1,m+1):
                out=target>=i if m==1 else (target>=i and levels[n]>=i-1) or levels[n]>=i+1
                tables[i-1].append(int(out));checks+=1;admissible_cases+=int(valid)
        for bit,truth in zip(bitnames(n,m),tables):
            rows[bit]=primes(support,truth)
            parsed=parse_bnet(bit+', '+rows[bit])[bit]
            need(table(parsed,support)==bytes(truth),'DNF differs from direct SBML evaluation: '+bit)
    inputs=sorted(n for n,(_,c) in species.items() if c);order=inputs+sorted(set(rows)-set(inputs))
    text='# Derived from BioModels MODEL2004040001 (CC0); see sources/ and MODEL-CONVERSION.md.\ntargets, factors\n'+''.join(n+', '+rows[n]+'\n' for n in order)
    return text,{'species':51,'transitions':41,'rules':56,'conversion_local_cases':checks,'admissible_local_cases':admissible_cases}

def parse_bnet(raw):
    out={}
    for line in raw.splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line.startswith('targets,'):continue
        n,e=map(str.strip,line.split(',',1));need(n not in out,'duplicate bit')
        out[n]=ast.parse(e.replace('!',' not ').replace('&',' and ').replace('|',' or ').strip(),mode='eval').body
    return out

def ev(t,s):
    if isinstance(t,ast.Name):return s[t.id]
    if isinstance(t,ast.UnaryOp) and isinstance(t.op,ast.Not):return not ev(t.operand,s)
    need(isinstance(t,ast.BoolOp),'invalid Boolean expression')
    if isinstance(t.op,ast.And):return all(ev(c,s) for c in t.values)
    need(isinstance(t.op,ast.Or),'invalid Boolean operator');return any(ev(c,s) for c in t.values)
def support(t):return sorted({x.id for x in ast.walk(t) if isinstance(x,ast.Name)})
def table(t,ss):return bytes(int(ev(t,dict(zip(ss,v)))) for v in itertools.product((0,1),repeat=len(ss)))

def check_reference(generated,record):
    parsed=parse_bnet(generated);need(list(parsed)==record['nodes'],'bit order mismatch')
    count=0
    for row in record['rules']:
        t=parsed[row['node']];ss=row['support']
        need(set(support(t))<=set(ss),'new support beyond reference')
        b=table(t,ss);need(len(b)==row['assignments'] and sha(b)==row['truth_sha256'],'local truth mismatch: '+row['node']);count+=len(b)
    need(len(record['rules'])==56 and {r['node'] for r in record['rules']}==set(parsed),'reference coverage')
    return count

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--build',action='store_true');ap.add_argument('--reference',type=Path)
    a=ap.parse_args();start=time.monotonic();generated,stats=generate(ROOT/'sources/Selvaggio_etal_2020.sbml')
    path=ROOT/'inputs/biomodels-derived.bnet';record_path=ROOT/'verification/model-comparison.json'
    if a.reference:
        need(a.build,'--reference is a one-time build option')
        raw=a.reference.read_bytes();old=parse_bnet(raw.decode());new=parse_bnet(generated)
        need(list(old)==list(new),'reference order');rows=[]
        for n,t in old.items():
            ss=sorted(set(support(t))|set(support(new[n])));v=table(t,ss)
            need(v==table(new[n],ss),'full local comparison failed: '+n)
            rows.append({'node':n,'support':ss,'assignments':len(v),'truth_sha256':sha(v)})
        record={'status':'PASS','method':'direct enumeration of every local Boolean assignment; SHA-256 records retained for offline replay','reference_sha256':sha(raw),'reference_size':len(raw),'reference_commit':'866a84d57935735ea781b0cc96e6df74a3ac0b52','reference_url':'https://raw.githubusercontent.com/hklarner/pyboolnet/866a84d57935735ea781b0cc96e6df74a3ac0b52/pyboolnet/repository/selvaggio_emt/selvaggio_emt.bnet','reference_bundled':False,'nodes':list(old),'rules':rows}
        record_path.write_text(json.dumps(record,indent=2)+'\n')
    record=json.loads(record_path.read_text());stats['reference_local_cases']=check_reference(generated,record)
    if a.build:path.write_text(generated)
    else:need(path.read_text()==generated,'generated model differs from deterministic SBML conversion')
    # Check independently parsed generated DNF against the directly evaluated SBML
    # truth tables through deterministic regeneration plus recorded full comparison.
    stats.update(status='PASS',sbml_sha256=SOURCE_SHA,generated_sha256=sha(generated.encode()),wall_seconds=time.monotonic()-start,reference_file_required=False)
    Path(a.output).write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats))
if __name__=='__main__':main()
