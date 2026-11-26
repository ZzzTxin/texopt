"""实际编译合成原稿，并运行现有texopt；每一步保存证据。"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from texopt import engine,perceive as P,score as S,proposal,advise
from texopt.core import Optimizer,_static_perception
from texopt.requirements import Requirement
OUT=ROOT/'合成排版演示案例集'
HERE=Path(__file__).resolve().parent
KEYS=['01_段落与间距混乱','02_图形超宽与浮动混乱','03_表格与长链接溢出']
DELIVERY_FOLDERS={'03_表格与长链接溢出':'03_长标识符与链接溢出'}

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def req():
    return Requirement(content_hard=True,preserve_figures=True,allow_geometry_tune=False,
        strip_reading_aids=False,remove_warning_boxes=False,aesthetic_shadow=False,
        max_iterations=30,verbose=True,shrink_oversized_figures=False)
def snap(per,original):
    return {'pages':per.pages,'score':S.total_score(per,req(),original),
        'counts':{k:len(per.issues.get(k,[])) for k in ['overfull','underfull','vbox','floats','tables_overwide','warnings']},
        'issues':per.issues,'visual':per.visual,'source_summary':per.source,'compile_ok':per.ok,
        'visual_defects':S.visual_defects(per)}
def paths(key):
    d=OUT/DELIVERY_FOLDERS.get(key,key);return d,d/'原始源码',HERE/'runs'/key
def original(key):return _static_perception(str(paths(key)[1]/'main.tex'))

def baseline(key):
    d,src,work=paths(key);work.mkdir(parents=True,exist_ok=True)
    target=work/'before'
    if (work/'before.json').exists():return read(work/'before.json')
    shutil.copytree(src,target)
    r=engine.compile_tex(str(target/'main.tex'),passes=2,timeout=45)
    (work/'before_compile.txt').write_text(r.log,encoding='utf-8')
    if not r.ok:raise RuntimeError(str(r.first_error)+'\n'+r.log[-2200:])
    per=P.perceive(str(target/'main.tex'),req());assert per.ok
    data=snap(per,original(key));write(work/'before.json',data)
    shutil.copy2(target/'main.pdf',d/'原稿.pdf')
    print(json.dumps({'case':key,'baseline':True,'pages':data['pages'],'score':data['score'],'counts':data['counts']},ensure_ascii=False),flush=True)
    return data

def optimize(key):
    d,src,work=paths(key);b=baseline(key)
    if (work/'rule.json').exists():return
    target=work/'after';shutil.copytree(work/'before',target)
    opt=Optimizer(str(src/'main.tex'),req(),str(target),resume=True)
    result=opt.run();write(work/'rule_result.json',result)
    if result['status']=='FAILED':raise RuntimeError(str(result))
    per=P.perceive(str(target/'main.tex'),req());data=snap(per,original(key))
    data.update({'result':result,'records':opt.records})
    write(work/'rule.json',data);shutil.copy2(target/'main.tex',work/'rule.tex');shutil.copy2(target/'main.pdf',work/'rule.pdf')
    print(json.dumps({'case':key,'rule_status':result['status'],'pages':data['pages'],'score':data['score'],'accepted':result['accepted']},ensure_ascii=False),flush=True)

def model_round(key,proposal_path):
    d,src,work=paths(key);doc=read(proposal_path);round_no=doc['round']
    if (work/f'model_round{round_no}.json').exists():raise RuntimeError('拒绝覆盖已执行轮次')
    target=work/'after';opt=Optimizer(str(src/'main.tex'),req(),str(target),resume=True)
    if (work/'latest_model.json').exists():prior=read(work/'latest_model.json')
    else:prior=read(work/'rule.json')
    opt.records=list(prior['records']);opt.iter=max((r['iteration'] for r in opt.records),default=0)
    opt.accepted=sum(r['accepted'] for r in opt.records);opt.attempts=len(opt.records)
    if (work/'failed_proposals.json').exists():opt._llm_failed=set(read(work/'failed_proposals.json'))
    before=read(work/'before.json');s=before['score']
    opt.baseline={'a':s['a'],'i':s['i'],'pages':before['pages'],'l':len(s['l']),'p':s['p'],'m1':s['m1'],'m2':s['m2']}
    # 请求包为当前真实状态，随后仅执行结构化白名单动作。
    opt.emit_request(round_no=round_no,with_visual=True,visual_dpi=90)
    shutil.copy2(target/'llm_request.json',work/f'request_round{round_no}.json')
    outcome=opt.apply_proposals(proposal.parse_proposals(doc)['items']);write(work/f'model_round{round_no}.json',{'proposals':doc,'outcome':outcome})
    per=P.perceive(str(target/'main.tex'),req());cur=S.total_score(per,req(),original(key))
    result=opt.finalize(per=per,cur=cur);data=snap(per,original(key))
    data.update({'result':result,'records':opt.records,'outcome':outcome})
    write(work/'latest_model.json',data);write(work/'failed_proposals.json',sorted(opt._llm_failed))
    shutil.copy2(target/'main.pdf',work/f'model_round{round_no}.pdf')
    print(json.dumps({'case':key,'model_round':round_no,'outcome':outcome,'pages':data['pages'],'score':data['score']},ensure_ascii=False),flush=True)

def restart_model(key):
    # 原稿不变。旧规则输出作为失败参数尝试留档，模型在新分支从原稿重提，
    # 不直接删除已插入的断词点，也不在白名单之外改正文。
    d,src,work=paths(key);old=work/'after';archive=work/'rule_pilot_after'
    assert old.resolve().is_relative_to(HERE.resolve()) and archive.resolve().is_relative_to(HERE.resolve())
    assert old.exists() and not archive.exists()
    old.rename(archive)
    shutil.copytree(work/'before',old)
    b=read(work/'before.json')
    write(work/'latest_model.json',{**b,'records':[],'result':{'status':'MODEL_RESTART_FROM_FROZEN_ORIGINAL'}})
    write(work/'model_restart.json',{'reason':'规则默认step=12断词仍有37.01208pt溢出；留档后从同一冻结原稿使用模型step=4提案。',
        'original_source_changed':False,'old_rule_output_archived':'rule_pilot_after','direct_body_rewrite':False})

def audit(key):
    d,src,work=paths(key);target=work/'after';a=(src/'main.tex').read_text(encoding='utf-8');b=(target/'main.tex').read_text(encoding='utf-8')
    m=read(d/'合成来源与原稿清单.json');hashes=m['frozen_original_hashes']
    unchanged=all(hashlib.sha256((src/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    assets=all(hashlib.sha256((target/p).read_bytes()).hexdigest()==h for p,h in hashes.items() if p!='main.tex')
    sp=importlib.util.spec_from_file_location('runner',ROOT/'docs/case_studies/run_cases.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
    result={'synthetic':True,'original_unchanged':unchanged,'normalized_main_text_preserved':S.semantic_diff(a,b,req())['preserved'],
      'display_math_contents_preserved':r.display_math(a)==r.display_math(b),'figure_files_unchanged':assets,
      'figure_fingerprints_preserved':[(f['kind'],f['fingerprint']) for f in P.parse_source(a)['figures']]==[(f['kind'],f['fingerprint']) for f in P.parse_source(b)['figures']]}
    result['pass']=all(v for k,v in result.items() if k!='synthetic')
    assert result['pass'],result
    write(work/'integrity.json',result);return result

def finalize(key):
    d,src,work=paths(key);target=work/'after';last=None;checks=[]
    for _ in range(3):
        per=P.perceive(str(target/'main.tex'),req());assert per.ok
        data=snap(per,original(key));sig={k:data[k] for k in ['pages','score','counts']};checks.append(sig)
        if sig==last:break
        last=sig
    else:raise RuntimeError('final measurements not stable')
    prior=read(work/'latest_model.json') if (work/'latest_model.json').exists() else read(work/'rule.json')
    data['records']=prior['records'];data['stable_recompile']=True;data['stability_checks']=checks;data['integrity']=audit(key)
    opt=Optimizer(str(src/'main.tex'),req(),str(target),resume=True)
    opt.accepted=sum(r['accepted'] for r in data['records']);opt.attempts=len(data['records'])
    data['program_status']=opt.exit_status(data['score'],data['visual_defects'])
    write(work/'final.json',data)
    out=d/'模型处理后源码'
    assert not out.exists(),'不覆盖已交付稿'
    shutil.copytree(src,out);shutil.copy2(target/'main.tex',out/'main.tex')
    shutil.copy2(target/'main.pdf',d/'模型处理后.pdf')
    proof=d/'运行证据';proof.mkdir(exist_ok=True)
    for name in ['before.json','rule.json','rule_result.json','final.json','integrity.json']:
        shutil.copy2(work/name,proof/name)
    for name in work.glob('model_round*.json'):shutil.copy2(name,proof/name.name)
    for name in work.glob('request_round*.json'):shutil.copy2(name,proof/name.name)
    (proof/'源码差异.patch').write_text(''.join(difflib.unified_diff((src/'main.tex').read_text(encoding='utf-8').splitlines(True),(target/'main.tex').read_text(encoding='utf-8').splitlines(True),fromfile='原稿/main.tex',tofile='模型处理后/main.tex')),encoding='utf-8')
    print(json.dumps({'case':key,'final':True,'pages':data['pages'],'score':data['score'],'status':data['program_status'],'integrity':data['integrity']},ensure_ascii=False),flush=True)

def one(item):
    mode,key=item
    try:
        if mode=='baseline':baseline(key)
        else:optimize(key)
    except Exception as e:write(paths(key)[2]/(mode+'_error.json'),{'error':type(e).__name__,'detail':str(e)});print(key,type(e).__name__,str(e),flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['baseline','optimize','model','restart_model','finalize']);ap.add_argument('key',nargs='?',default='all');ap.add_argument('proposals',nargs='?');ap.add_argument('--jobs',type=int,default=1);a=ap.parse_args()
    keys=KEYS if a.key=='all' else [a.key]
    if a.mode=='model':model_round(a.key,Path(a.proposals));return
    if a.mode=='restart_model':restart_model(a.key);return
    if a.mode=='finalize':
        for key in keys:finalize(key)
    elif a.jobs>1:
        with ProcessPoolExecutor(max_workers=min(a.jobs,3)) as pool:list(pool.map(one,[(a.mode,k) for k in keys]))
    else:
        for key in keys:one((a.mode,key))
if __name__=='__main__':main()
