"""整理三个合成案例的中文Word、全部页面比较与机器可读核验。"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile

import fitz
from docx import Document
from docx.shared import Cm

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'合成排版演示案例集'
sp=importlib.util.spec_from_file_location('document_helpers',ROOT/'workbench/case_delivery/build_case_collection.py')
H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)
KEYS=['01_段落与间距混乱','02_图形超宽与浮动混乱','03_表格与长链接溢出']
FOLDERS={KEYS[2]:'03_长标识符与链接溢出'}
DESCS={
 KEYS[0]:{'title':'段落与间距混乱','issue':'明确构造的正文误分页、30mm/26mm正向大空白、超大标题与章节字号、局部字号和过疏列表。',
 'effect':'规则闭环删除了位于同一小节连续正文之间的误分页及两处明确注入的大vspace，统一标题和正文局部字号、收紧列表及过大的段距。原稿3页变为2页，首尾阅读层次更连续。末页因内容结束产生的留白保留，不把填满页面当作目标。',
 'model':'模型检查全部页面后提出流程图!htbp定点位置提案；全局验收没有改善，实际回滚。最终保留规则输出，不能把该提案写成已接受的模型修改。',
 'remaining':'主要人工构造的间距和字号缺陷已修复；程序仍因第二页自然尾部留白给出NEEDS_REVIEW。未为消除这个状态而压缩版心、加内容或删正常间隔。',
 'panels':[(1,1)]},
 KEYS[1]:{'title':'双栏图形越界与浮动关系','issue':'双栏稿内使用112mm和108mm绝对图宽，明显超过单栏宽度，并用H强排；原稿中图形覆盖邻栏文字。另有过大列表和段距。',
 'effect':'规则先处理H强排和列表间距，模型第一轮将两图分别定点改为0.95\\linewidth，消除97.187pt和85.806pt的跨栏溢出。完整页复核又发现通用tbp把图放到了摘要之前，模型第二轮使用!b恢复摘要和说明在前、图在页底的顺序。正文、题注和两份原图二进制均不改。',
 'model':'实际接受4条模型提案：两张图的定点宽度与两张图的定点位置。低于150mm固定阈值的绝对图宽需要结合真实栏宽判断，这一案例直接展示模型在环的作用。',
 'remaining':'跨栏遮挡已消除，原稿与处理稿都为2页。11pt段距的归一化曾因M1变差回滚，因此仍保留；自然尾页留白也保留。M2最终高于原稿，不能称所有软视觉指标一起改善。',
 'panels':[(1,1)]},
 KEYS[2]:{'title':'长标识符与链接断行','issue':'120字符连续标识符和长URL溢出版心，24mm人为大空白及20pt列表间距使页面疏松。表格本身可放进版心，不虚构其超宽问题。',
 'effect':'默认规则试排每12字符加断词点后仍有37.012pt溢出，因此归档该输出、回到同一冻结原稿重新提出模型方案。模型使用step=4添加可选断词点、加载xurl、删除24mm显式空白并规范列表与段距。最终overfull由2条降为0，编号和链接的字符内容未改。',
 'model':'从同一冻结原稿恢复模型分支，7条白名单提案实际接受；没有直接删除既有断词点或在白名单之外重写正文。旧规则试排、重启原因和最终模型轨迹均保存，旧失败输出未混入最终稿。',
 'remaining':'仍有1条underfull提示和自然末页余白，程序保留NEEDS_REVIEW；这不改变“原有越界文字已收回版心”的实际效果。M2略升，照实记录。',
 'panels':[(2,1)]}
}

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def folder(key):return OUT/FOLDERS.get(key,key)

def doc(title):
 d=H.document(title,'合成演示稿｜人工构造排版缺陷｜非真实发表论文')
 d.sections[0].footer.paragraphs[0].text='texopt 合成排版演示案例集 · 2026-11-25'
 return d

def panels(documents,indices,path,labels=None):
 result=fitz.open()
 maximum=max(len(d) for d in documents)
 use=indices if indices is not None else [(i,i) for i in range(maximum)]
 for a,b in use:
  page_refs=[(documents[0],a),(documents[1],b)]
  w=documents[0][0].rect.width;h=documents[0][0].rect.height
  p=result.new_page(width=2*w+42,height=h+56)
  p.draw_rect(p.rect,color=None,fill=(.94,.96,.98));p.insert_font(fontname='zh',fontfile='C:/Windows/Fonts/simhei.ttf')
  for col,(d,i) in enumerate(page_refs):
   x=14+col*(w+14)
   text=(labels[col] if labels else ('混乱原稿' if col==0 else '模型处理后'))+f'｜第{i+1}页'
   p.insert_text((x,27),text,fontname='zh',fontsize=17)
   if i<len(d):p.show_pdf_page(fitz.Rect(x,42,x+w,42+h),d,i)
   else:p.insert_text((x+40,180),'此版本无对应页；内容已重新流动。',fontname='zh',fontsize=17)
 result.subset_fonts();result.save(path,garbage=4,deflate=True)
 if len(result)==1:result[0].get_pixmap(dpi=125,alpha=False).save(path.with_suffix('.png'))
 result.close()

def metrics(b,a):
 rows=[['总页数',b['pages'],a['pages']]]
 for key,name in [('overfull','正文行溢出'),('underfull','正文行欠满'),('vbox','垂直盒子警告'),('floats','浮动体警告')]:rows.append([name,b['counts'][key],a['counts'][key]])
 for key,name in [('p','P：缺陷量'),('i','I：干预代价'),('m1','M1 = 15P + I'),('m2','M2：软视觉评分')]:rows.append([name,f"{b['score'][key]:.3f}",f"{a['score'][key]:.3f}"])
 return rows

def report(key):
 f=folder(key);run=HERE/'runs'/key;cfg=DESCS[key]
 before=read(run/'before.json');after=read(run/'final.json');meta=read(f/'合成来源与原稿清单.json')
 assert after['integrity']['pass'] and after['stable_recompile']
 rd=[read(p) for p in sorted(run.glob('model_round*.json'))]
 with fitz.open(f/'原稿.pdf') as a,fitz.open(f/'模型处理后.pdf') as b:
  compare=f/'页面对比';compare.mkdir(exist_ok=True)
  panels([a,b],None,compare/'全部页面前后对照.pdf')
  pairs=[(x-1,y-1) for x,y in cfg['panels']]
  panels([a,b],pairs,compare/'关键页面比较.pdf')
  # 预览全部页面的低分辨率索引，明确只是浏览图。
  from PIL import Image,ImageDraw,ImageFont
  canvas=Image.new('RGB',(960,max(len(a),len(b))*700),'#e4e8ed');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
  for i in range(max(len(a),len(b))):
   for c,document in enumerate([a,b]):
    if i>=len(document):continue
    pix=document[i].get_pixmap(dpi=65,alpha=False);im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);im.thumbnail((465,665));x=c*480+7;y=i*700+28;canvas.paste(im,(x,y));draw.text((x,y-25),f"{'原稿' if c==0 else '处理后'}第{i+1}页",font=font,fill='black')
  canvas.save(compare/'全部页面缩略图.png')
 proof=f/'运行证据'
 for p in run.glob('*compile.txt'):shutil.copy2(p,proof/p.name)
 if (run/'model_restart.json').exists():shutil.copy2(run/'model_restart.json',proof/'模型重启原因.json')
 d=doc('合成案例｜'+cfg['title'])
 d.add_heading('一、来源与演示边界',1)
 H.para(d,'这是由本项目生成的合成原稿，不是真实论文，不来自任何会议或期刊。正文、数值、图形均为演示内容，所有数字不代表真实观测或实验结论。问题由生成脚本显式设置，用于展示既有排版动作与模型在环，不能作为真实稿件上的泛化效果证据。')
 H.para(d,'原稿生成后冻结。修复阶段只调用白名单动作；不删除、补写或改写正文，不更换数据、公式、题注或原图。图形是程序生成的矢量示意图，两个版本的原图文件哈希一致。')
 d.add_heading('二、原稿刻意设置的问题',1);H.para(d,cfg['issue'])
 d.add_heading('三、实际执行过程',1)
 H.para(d,'使用现有texopt评分和验收：先检查gate，主评分M1=15P+I优先，仅在M1持平时比较M2。λ=0，无页数目标，未调整全局页边距或基础字号。所有保留动作都实际编译验证，失败候选回滚。')
 H.para(d,cfg['model'])
 rows=[]
 for r in after['records']:rows.append(['模型提案' if r.get('source')=='llm' else '确定性规则',r['action'],'接受' if r['accepted'] else '回滚',r.get('detail','')])
 H.table(d,['来源','实际动作','结果','理由／记录'],rows)
 if key==KEYS[2]:H.para(d,'本表仅统计最终模型分支；未采用的默认规则分支另外保存在rule.json和模型重启原因中，不重复累计为最终改动。')
 d.add_heading('四、量化变化',1);H.table(d,['指标','混乱原稿','最终处理后'],metrics(before,after))
 H.para(d,'分数下降不自动等于所有视觉指标改善。M2在部分案例中上升，仍如实展示；没有更改权重去迎合展示结果。')
 d.add_heading('五、前后实际效果',1);H.para(d,cfg['effect'])
 d.add_picture(str(compare/'关键页面比较.png'),width=Cm(16.7))
 H.para(d,'图：直接导入两个实际编译PDF的页面，页码见图上方。内容会因排版重新流动；该图是便于浏览的比较，不代替分别提供的两份完整PDF。')
 d.add_heading('六、保留的余白与未决项',1);H.para(d,cfg['remaining'])
 H.para(d,'程序状态：'+after['program_status']+'。主要构造缺陷的修复与程序的粗粒度尾部空白提示分别记录，不为了把状态改成DONE而继续填满页面。')
 if after['visual_defects']:H.table(d,['页码','程序提示','级别','量值'],[[x.get('page'),x['kind'],x['severity'],x.get('metric')] for x in after['visual_defects']])
 d.add_heading('七、复现和完整性',1)
 H.para(d,'在原始源码或模型处理后源码目录运行两遍：xelatex -interaction=nonstopmode -halt-on-error main.tex。需要标准TeX Live和中文字体。图文件、宏包引用、完整源码均已提供。')
 H.table(d,['核验项目','结果'],[[k,'通过' if v else '未通过'] for k,v in after['integrity'].items() if k not in ['synthetic','pass']])
 H.para(d,'归一化正文保持是严格的内容比对，不是语义等价证明。最终稿已连续重编译确认页数、日志和评分稳定。')
 saved=H.save_word(d,f/'优化前后总结.docx')
 note='本目录是合成演示，非真实论文。\n主文件：main.tex\n编译器：XeLaTeX（TeX Live 2024，Windows中文字体）\n在原始源码或模型处理后源码目录中连续编译两遍。\n正文和原图在优化前后保持，只有白名单排版命令发生变化。\n完整原稿：原稿.pdf；完整输出：模型处理后.pdf。\n'
 (f/'编译说明.txt').write_text(note,encoding='utf-8')
 return {'id':key,'folder':f.name,'title':cfg['title'],'before_pages':before['pages'],'after_pages':after['pages'],
  'before_score':before['score'],'after_score':after['score'],'before_counts':before['counts'],'after_counts':after['counts'],
  'rule_accepted':sum(x['accepted'] and x.get('source')=='rule' for x in after['records']),
  'model_accepted':sum(x['accepted'] and x.get('source')=='llm' for x in after['records']),
  'rolled_back':sum(not x['accepted'] for x in after['records']),
  'program_status':after['program_status'],'word_file':saved.name,
  'original_pdf_sha256':sha(f/'原稿.pdf'),'after_pdf_sha256':sha(f/'模型处理后.pdf'),
  'integrity_pass':True,'deliberately_synthetic':True}

def overall(items):
 d=doc('三个合成排版案例｜总体总结')
 d.add_heading('一、为什么改用合成原稿',1)
 H.para(d,'已停止扩展真实发表论文的筛选。真实作者稿件往往已经有较成熟的版式，强行改动可能破坏必要结构。本组改为明确构造缺陷的合成稿，让排版动作的效果更容易观察，同时不把它们伪装成真实论文。此前真实稿件和失败尝试保留为历史材料，不作为这组三个最终展示例子。')
 d.add_heading('二、三个展示主题',1)
 H.table(d,['样本','构造问题','主要实际修复'],[[x['folder'],DESCS[x['id']]['issue'],DESCS[x['id']]['effect']] for x in items])
 d.add_heading('三、前后实测数据',1)
 H.table(d,['样本','页数','overfull','M1','M2','实际模型接受'],[[x['folder'],f"{x['before_pages']}→{x['after_pages']}",f"{x['before_counts']['overfull']}→{x['after_counts']['overfull']}",f"{x['before_score']['m1']:.3f}→{x['after_score']['m1']:.3f}",f"{x['before_score']['m2']:.3f}→{x['after_score']['m2']:.3f}",x['model_accepted']] for x in items])
 H.para(d,'这是一组受控展示，不是随机基准。没有真实实验数据，也不据此推断真实稿件成功率。规则与模型提案分开计数；第一例的主要收益来自确定性规则，第二例和第三例展示模型的定点参数决策。')
 d.add_heading('四、完整文档与必要留白',1)
 H.para(d,'每个样本均提供两份完整PDF和对应工程，可逐页并排查看。末页因内容结束产生的正常空白保留；模型没有压缩全局版心或补写内容去填满页面。像素检测器仍可能把这些自然尾白标为high，原始NEEDS_REVIEW状态保留，没有改评分或隐藏提示。')
 for x in items:
  d.add_heading(x['folder'],2);H.para(d,DESCS[x['id']]['model']);H.para(d,DESCS[x['id']]['remaining'])
 d.add_heading('五、内容完整性与可追溯性',1)
 H.para(d,'生成原稿后记录每个文件哈希；优化只发生在副本。三个案例均通过归一化正文、显示公式内容、浮动体内容指纹和图文件字节哈希检查。各提案均通过白名单校验、整篇重编译和现行验收函数，拒绝的候选不计为应用。')
 H.para(d,'第三例默认断词步长12的试排没有完全解决溢出，已留档。模型从同一冻结原稿重新提出步长4的方案，最终修复了溢出。保留这一过程是为了区分参数调整和直接改写文本。')
 d.add_heading('六、交付文件',1)
 H.para(d,'每例含：原始源码、模型处理后源码、原稿.pdf、模型处理后.pdf、优化前后总结.docx、运行证据、页面对比及合成来源清单。根目录提供本总体总结、目录索引、核验结果、生成与运行脚本，以及便于浏览的前后比较总览。')
 p=H.save_word(d,OUT/'总体总结.docx');return p

def validate(items):
 for x in items:
  d=OUT/x['folder'];meta=read(d/'合成来源与原稿清单.json');assert meta['synthetic']
  for rel,h in meta['frozen_original_hashes'].items():
   assert sha(d/'原始源码'/rel)==h
   if rel!='main.tex':assert sha(d/'模型处理后源码'/rel)==h
  for name,n in [('原稿.pdf',x['before_pages']),('模型处理后.pdf',x['after_pages'])]:
   with fitz.open(d/name) as doc:assert len(doc)==n
  word=Document(d/x['word_file']);text='\n'.join(p.text for p in word.paragraphs)
  assert '合成' in text and '未决' in text and len(word.inline_shapes)>0
  with zipfile.ZipFile(d/x['word_file']) as z:assert z.testzip() is None
 return {'status':'pass','synthetic':True,'case_count':3,'complete_pdfs':6,'word_documents':4,
   'frozen_originals_unchanged':True,'body_and_figures_preserved':True,'all_final_measurements_stable':True,
   'scope':'合成演示完整性与交付核验；不是所有审美指标都改善、也不是真实论文泛化效果证明。'}

items=[report(k) for k in KEYS];overall_path=overall(items)
write(OUT/'目录索引.json',{'synthetic':True,'date':'2026-11-25','overall_word':overall_path.name,'cases':items})
write(OUT/'交付核验.json',validate(items))
programs=OUT/'生成与运行脚本';programs.mkdir(exist_ok=True)
for n in ['build_originals.py','run_showcase.py','package_showcase.py']:shutil.copy2(HERE/n,programs/n)
for p in HERE.glob('proposals*.json'):shutil.copy2(p,programs/p.name)
# 生成脚本引用仓库texopt，复制归档用于追溯，不声称脱离仓库可运行优化器。
lines=['# 合成排版演示案例集','','**三个样本均由程序生成，非真实发表论文，图表与数值均为合成内容。**',
       '',f'先看[总体总结]({overall_path.name})；每个样本分别提供完整原稿与完整处理后PDF。','','| 样本 | 原稿 | 模型处理后 | 中文Word |','|---|---|---|---|']
for x in items:
 f=x['folder'];lines.append(f"| {f} | [完整原稿]({f}/原稿.pdf) | [完整处理稿]({f}/模型处理后.pdf) | [优化前后总结]({f}/{x['word_file']}) |")
lines+=['','每例的“页面对比/全部页面前后对照.pdf”可快速浏览，但不代替两个独立完整PDF。',
        '','优化前后正文、数据、公式、图文件不改。末页正常留白保留；程序的NEEDS_REVIEW状态和软视觉评分上升也如实记录，不为凑成功结论改权重。',
        '','复现：在“原始源码”或“模型处理后源码”目录用XeLaTeX编译main.tex两遍。需TeX Live及Windows中文字体。原稿工程与图表自包含；优化器脚本需要从texopt仓库环境运行。']
(OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
# 三个关键比较组成可直接浏览的总览，页面本体仍为矢量PDF。
overview=fitz.open()
for x in items:
 with fitz.open(OUT/x['folder']/'页面对比/关键页面比较.pdf') as d:overview.insert_pdf(d)
overview.save(OUT/'三个案例_前后效果总览.pdf',garbage=4,deflate=True);overview.close()
print(json.dumps({'output':str(OUT),'cases':3,'complete_pdfs':6,'word_documents':4,'verification':'pass'},ensure_ascii=False))
