#!/usr/bin/env python3
"""Verify saved certificates and independently reconstructed reachable sets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent


def need(ok, why):
    if not ok:
        raise ValueError(why)


def manifest_check(root):
    manifest = json.loads((root/'MANIFEST.json').read_text())
    seen = set()
    for row in manifest['files']:
        name = row['path']
        need(name not in seen,'Duplicate manifest path')
        seen.add(name)
        p = root/name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe manifest path')
        need(not p.is_symlink() and p.is_file(),'Manifest file missing or symlink: '+name)
        data = p.read_bytes()
        need(len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256'],'Manifest mismatch: '+name)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()
              and '.git' not in p.relative_to(root).parts and '__pycache__' not in p.relative_to(root).parts
              and p.name!='MANIFEST.json'}
    need(actual == seen,'Unlisted or missing packet file')
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--budget-seconds',type=int,default=540)
    ap.add_argument('--output',help='New JSON receipt outside this package; default prints to stdout')
    ap.add_argument('--manifest-only',action='store_true')
    args = ap.parse_args()
    need(1 <= args.budget_seconds <= 600,'Budget must be 1..600 seconds')
    if args.output:
        output = Path(args.output).resolve()
        need(not output.exists(),'Refuse to overwrite receipt')
        need(ROOT not in output.parents,'Output must be outside the sealed package')
    started = time.monotonic()
    deadline = started+args.budget_seconds
    result = {'status':'RUNNING','python':sys.version,'platform':platform.platform(),
              'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'generation_run':False,'network_required':False,'stages':{},'negative_controls':[]}

    def run(script, extra, *, root=ROOT, optimize=False):
        remaining = deadline-time.monotonic()
        need(remaining>0,'Total wall-time budget exhausted')
        cmd = [sys.executable,'-I','-B']+(['-O'] if optimize else [])+[str(root/script)]+extra
        env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1')
        cp = subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True,timeout=remaining)
        return cp

    try:
        result['manifest_files'] = manifest_check(ROOT)
        if not args.manifest_only:
            with tempfile.TemporaryDirectory(prefix='release-observation-') as td:
                temp = Path(td)
                stages = [('model_conversion','scripts/convert_model.py',[]),
                          ('bdd_basic','scripts/bdd_check.py',['--mode','basic']),
                          ('saved_certificates','scripts/certificate_check.py',[]),
                          ('bdd_all_paths','scripts/bdd_check.py',['--mode','upper']),
                          ('unique_observation','scripts/unique_check.py',[]),
                          ('kernel_audit','scripts/kernel_audit.py',[])]
                for label,script,extra in stages:
                    target = temp/(label+'.json')
                    cp = run(script,extra+['--output',str(target)])
                    need(cp.returncode==0, label+' failed: '+cp.stderr[-2000:]+cp.stdout[-2000:])
                    d = json.loads(target.read_text())
                    need(d['status']=='PASS',label+' did not report PASS')
                    result['stages'][label] = d
                    print(label+': PASS',file=sys.stderr,flush=True)
                # Both verifiers must consume the same witness set and model.
                combined = json.loads((ROOT/'inputs/witnesses.json').read_text())
                lower = json.loads((ROOT/'certificates/lower-result.json').read_text())
                upper = json.loads((ROOT/'certificates/upper-result.json').read_text())
                initial = json.loads((ROOT/'certificates/initial-fixed-points.json').read_text())
                need(combined['witnesses']==lower['witnesses'],'Witness consumers differ')
                need(combined['S']==upper['S'],'S consumers differ')
                need(combined['initial_models']==initial['models'],'Initial model consumers differ')
                unique=result['stages']['unique_observation']
                saved=json.loads((ROOT/'certificates/optimal-sets.json').read_text())
                for key in ('original_S','common_sets','classification','valid_optimal_sets','deletion_certificates'):
                    need(unique[key]==saved[key],'Optimal-set certificate mismatch: '+key)
                need(unique['valid_optimal_sets']==[sorted(combined['S'])],'Unique optimum differs from verified S')
                need(unique['verdict']['unique_optimal_14_set'] and unique['verdict']['every_bit_essential_within_each_reported_set'],'Uniqueness or deletion necessity failed')
                # Mutation checks bypass the manifest only by invoking the semantic
                # certificate consumer directly on temporary copies, never on ROOT.
                cases = ['trace_bit','release_assignment','proof_reason','sensor_count','cnf_model_binding']
                for label in cases:
                    trial = temp/label
                    shutil.copytree(ROOT,trial,ignore=shutil.ignore_patterns('.git','__pycache__'))
                    if label in ('trace_bit','release_assignment'):
                        path = trial/'certificates/lower-result.json'
                        d = json.loads(path.read_text())
                        if label=='trace_bit':
                            f = d['witnesses'][0]['trace'][2]
                            f['state'] = format(int(f['state'],16)^1,'014x')
                        else:
                            d['witnesses'][0]['release_state']['PI3K'] ^= 1
                    elif label=='cnf_model_binding':
                        path = trial/'certificates/initial-fixed-points.json'
                        d = json.loads(path.read_text())
                        # Change a conjunction consistently so parsing succeeds;
                        # the exhaustive CNF-to-SBML semantic binding must fail.
                        need(d['cnf'][20]==[-57,12] and d['cnf'][22]==[57,-12,-11],'CNF mutation fixture')
                        d['cnf'][20]=[-57,-12];d['cnf'][22]=[57,12,-11]
                    else:
                        path = trial/'certificates/upper-result.json'
                        d = json.loads(path.read_text())
                        if label=='sensor_count':
                            d['S'].pop()
                        else:
                            tree = d['queries'][0]['proof']
                            # A non-unit reason cannot justify this fresh literal.
                            need(bool(tree['units']),'Expected nonempty saved unit proof')
                            tree['units'][0]['literal'] = 1000000
                    path.write_text(json.dumps(d)+'\n')
                    cp = run('scripts/certificate_check.py',['--output',str(temp/(label+'-result.json'))],root=trial)
                    need(cp.returncode!=0 and 'AssertionError' in cp.stderr,'Mutation not semantically rejected: '+label)
                    result['negative_controls'].append({'mutation':label,'checker':'saved_certificates','rejected':True})
                for label in ('sbml_source_hash','derived_formula','comparison_truth_hash'):
                    trial = temp/label
                    shutil.copytree(ROOT,trial,ignore=shutil.ignore_patterns('.git','__pycache__'))
                    if label=='sbml_source_hash':
                        path=trial/'sources/Selvaggio_etal_2020.sbml'
                        path.write_bytes(path.read_bytes().replace(b'qual:resultLevel="1"',b'qual:resultLevel="0"',1))
                        expected='SBML source hash mismatch'
                    elif label=='derived_formula':
                        path=trial/'inputs/biomodels-derived.bnet'
                        text=path.read_text();need('AKT, ILK&PI3K' in text,'formula mutation fixture')
                        path.write_text(text.replace('AKT, ILK&PI3K','AKT, ILK&!PI3K'))
                        expected='generated model differs'
                    else:
                        path=trial/'verification/model-comparison.json'
                        data=json.loads(path.read_text());data['rules'][0]['truth_sha256']='0'*64
                        path.write_text(json.dumps(data));expected='local truth mismatch'
                    cp=run('scripts/convert_model.py',['--output',str(temp/(label+'.json'))],root=trial)
                    need(cp.returncode!=0 and expected in cp.stderr,'Conversion mutation not rejected: '+label)
                    result['negative_controls'].append({'mutation':label,'checker':'model_conversion','rejected':True})
                cp = run('scripts/certificate_check.py',['--output',str(temp/'optimized.json')],optimize=True)
                need(cp.returncode!=0 and 'Assertions must be enabled' in cp.stderr,'Optimized checker accepted')
                result['negative_controls'].append({'mutation':'python_-O','rejected':True})
                bad = temp/'tampered-manifest'
                shutil.copytree(ROOT,bad,ignore=shutil.ignore_patterns('.git','__pycache__'))
                f = bad/'inputs/witnesses.json'
                f.write_bytes(f.read_bytes()+b'\n')
                try:
                    manifest_check(bad)
                except ValueError as e:
                    need('Manifest mismatch' in str(e),'Wrong manifest rejection')
                else:
                    raise ValueError('Manifest accepted a changed witness file')
                result['negative_controls'].append({'mutation':'witness_file_hash','rejected':True})
        result['status'] = 'PASS'
    except Exception as e:
        result['status'],result['error'] = 'FAIL',repr(e)
    result['wall_seconds'] = time.monotonic()-started
    result['max_parallel_compute_processes'] = 1
    text = json.dumps(result,indent=2)+'\n'
    if args.output:
        output.write_text(text)
    print(text,end='')
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
