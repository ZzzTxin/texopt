"""生成三个明确标注的合成排版原稿；生成后冻结正文、表格和图文件。"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import fitz

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'合成排版演示案例集'
CASES={
 '01_段落与间距混乱':{'title':'城市传感器数据处理流程','focus':'大标题、过大段距、正向大vspace、误插正文分页、局部字号、列表间距'},
 '02_图形超宽与浮动混乱':{'title':'边缘设备状态监测记录','focus':'双栏内使用超过栏宽的绝对图宽、H强排、图文浮动分配；保留模型定点修复空间'},
 '03_长标识符与链接溢出':{'title':'资源调度方案的合成记录','focus':'不可断长标识符、长URL、列表间距、正向大间距；已有表格内容和正常列宽保留'},
}
FONT=Path('C:/Windows/Fonts/simhei.ttf')

PARAS=[
 '本节用一个内容固定的演示任务说明排版过程。系统依次完成输入登记、格式检查、窗口划分和结果汇总。为了方便比较，两个版本保留完全相同的说明文字，不增加新的步骤，也不删除已有条件。这里关注的是信息能否按照清晰的顺序呈现，而不是某个算法取得了更好的研究结果。',
 '数据记录包含时间、通道名称和一个示意读数。相邻窗口可以共享边界样本，但汇总时不重复计算。缺失位置只保留占位标记，不使用虚构观测填补。本文列出的数字都是为了形成可重复的表格和图形而构造的演示数值，不来自设备、受试者或公开实验。',
 '处理流程先验证各列的类型，再检查同一窗口内的时间顺序。如果检查失败，窗口保持原样并附加状态标记。只有通过检查的窗口进入后续汇总。这样的约定使每个输出都能追溯到输入，也让排版前后的内容核对有明确依据。',
 '展示页面应让标题、说明和图表形成连续的阅读路径。必要的章节分隔、图表内部留白和图注间距应被保留。孤立的大空洞、越过版心的对象以及相互冲突的局部格式则需要单独判断，不能仅凭页面是否填满来评价质量。',
 '比较采用相同的纸张、版心和正文基础字号。两份文档的区别只允许落在已声明的排版命令上。表格数据、图形文件、公式内容和交叉引用在原稿生成后冻结，因此读者可以把注意力放在布局的变化，而不用猜测内容是否也被修改。',
 '结果记录分成处理状态和阅读检查两部分。处理状态说明文件能否编译、对象是否完整以及当前仍有哪些日志提示。阅读检查则关注图文距离、标题层次和是否出现遮挡。前者可以重复测量，后者需要结合整页图像检查，不能互相替代。',
 '对于正常范围内的空白，演示不要求进一步压缩。段落之间仍应有适当间隔，插图与图注之间仍应有视觉分离。改变浮动位置时还要重新检查整篇文档，因为前面一个对象的移动可能影响后面多个页面的断点。',
 '本文的目的不是给出真实应用的性能结论，而是形成一个可审计的排版案例。所有操作应记录修改位置、修改理由和验收结果。如果某个候选使全局结果变差，就恢复到修改之前；如果问题无法在既有动作范围内解决，则保留并明确说明。',
]

def paragraphs(indices):return '\n\n'.join(PARAS[i%len(PARAS)] for i in indices)+'\n\n'
def asset(path,name,kind):
 doc=fitz.open();p=doc.new_page(width=540,height=190)
 p.insert_font(fontname='zh',fontfile=str(FONT))
 p.insert_text((18,23),name+'（合成示意）',fontname='zh',fontsize=14,color=(.1,.18,.3))
 if kind=='flow':
  for i,label in enumerate(['输入记录','格式检查','窗口汇总','结果归档']):
   x=20+i*130;p.draw_rect(fitz.Rect(x,62,x+105,114),color=(.2,.35,.55),fill=(.88,.94,.99),width=1.2)
   p.insert_text((x+15,92),label,fontname='zh',fontsize=12)
   if i<3:p.draw_line((x+108,88),(x+126,88),color=(.2,.35,.55),width=2)
 else:
  p.draw_line((45,145),(495,145),color=(.25,.25,.25));p.draw_line((45,48),(45,145),color=(.25,.25,.25))
  colors=[(.18,.47,.74),(.88,.46,.18),(.2,.6,.43)]
  for j,(vals,color) in enumerate(zip([[33,45,57,69,74,81],[27,37,51,60,71,76],[24,35,44,58,66,70]],colors)):
   pts=[(62+i*77,145-v) for i,v in enumerate(vals)]
   for a,b in zip(pts,pts[1:]):p.draw_line(a,b,color=color,width=2)
   for pt in pts:p.draw_circle(pt,2,color=color,fill=color)
   p.insert_text((345,28+j*14),'方案'+chr(65+j),fontname='zh',fontsize=10,color=color)
 p.insert_text((18,178),'演示数据为人工构造，不代表真实实验结果。',fontname='zh',fontsize=9,color=(.35,.35,.35))
 doc.subset_fonts();doc.save(path,garbage=4,deflate=True);doc.close()

def preamble(title,extra='',twocol=False):
 options='UTF8,10pt,a4paper,fontset=windows'+(',twocolumn' if twocol else '')
 return (r'\documentclass['+options+r']{ctexart}'+'\n'+r'''
\usepackage[margin=25.4mm]{geometry}
\usepackage{graphicx,float,booktabs,amsmath,amssymb,enumitem,array}
\usepackage[hidelinks]{hyperref}
'''+extra+'\n'+r'\title{'+title+'}\n'+r'''\author{texopt 合成排版演示}
\date{}
\begin{document}
\maketitle
\begin{abstract}
本稿由程序生成，仅用于展示排版修复。正文、示意图和表格数值均为合成内容，
不是真实发表论文，也不代表真实研究结果。优化前后应保留相同的文字、公式、引用和图表内容。
\end{abstract}
''')

def case1():
 s=preamble(r'\Huge 合成案例一：城市传感器数据处理流程',r'''
\usepackage{titlesec}
\titleformat{\section}{\Huge\bfseries}{\thesection}{0.6em}{}
\setlength{\parskip}{20pt}
''')
 s+=r'\section{任务说明}'+'\n'+paragraphs([0,1])
 s+='% 注入的无结构用途错误分页：位于同一小节连续正文之间\n'+r'\newpage'+'\n\n'+paragraphs([2])
 s+=r'\vspace{30mm}'+'\n\n'+paragraphs([3])
 s+=r'\section{处理流程}'+'\n'+r'{\Large '+PARAS[4]+'}\n\n'+paragraphs([5])
 s+=r'\vspace{26mm}'+'\n\n'+r'''\begin{figure}[H]
\centering
\includegraphics[width=0.90\linewidth]{figs/flow.pdf}
\caption{固定的四步处理流程；图形文件在两份稿件中保持一致。}
\label{fig:flow}
\end{figure}
\begin{itemize}[itemsep=22pt,topsep=20pt,parsep=15pt]
\item 输入登记：只记录已有字段，不改写观测。
\item 类型检查：对异常窗口附加状态标记。
\item 结果汇总：每个窗口保留可追溯的编号。
\end{itemize}
'''+paragraphs([6])
 s+=r'\section{核对与结论}'+'\n'+paragraphs([7,4,5])+r'\end{document}'+'\n'
 return s

def case2():
 s=preamble('合成案例二：边缘设备状态监测记录',r'\setlength{\parskip}{11pt}',True)
 s+=r'\section{观察任务}'+'\n'+paragraphs([0,1])
 s+=r'''\begin{figure}[H]
\centering
% 112mm低于全局150mm阈值，但明显大于本例单栏宽度；留给模型定点提案。
\includegraphics[width=112mm]{figs/flow.pdf}
\caption{输入检查与汇总流程。图宽的错误设置不改变图中的流程内容。}
\label{fig:wideflow}
\end{figure}
'''+paragraphs([2,3])
 s+=r'\section{状态记录}'+'\n'+paragraphs([4])
 s+=r'''\begin{figure}[H]
\centering
\includegraphics[width=108mm]{figs/curves.pdf}
\caption{三组人工构造的示意数值，仅用于保持排版前后的图形内容一致。}
\label{fig:widecurves}
\end{figure}
'''+paragraphs([5,6])
 s+=r'''\begin{itemize}[itemsep=18pt,topsep=18pt]
\item 窗口边界与输入顺序保持一致。
\item 图文对应关系需要结合整页检查。
\item 图像文件不得在优化时重画或替换。
\end{itemize}
\section{讨论与结论}
'''+paragraphs([7,3,4,5])+r'\end{document}'+'\n'
 return s

def case3():
 s=preamble('合成案例三：资源调度方案的合成记录',r'\setlength{\parskip}{12pt}')
 s+=r'\section{记录约定}'+'\n'+paragraphs([0,1])
 s+=r'''\begin{table}[h!]
\centering
\caption{人工构造的任务记录，单元格内容在优化前后保持一致。}
\label{tab:wide}
\begin{tabular}{lrrl}
\toprule
任务说明 & 窗口数 & 示例值 & 状态 \\
\midrule
跨通道输入登记与时间戳顺序核验及缺失位置记录任务 & 12 & 0.35 & 已登记 \\
多窗口边界检查与重复条目排除及结果归档说明任务 & 18 & 0.42 & 已登记 \\
不同设备输入模式统一与异常状态标记及汇总任务 & 15 & 0.38 & 待核对 \\
固定处理流程的可重复运行与输出位置比对演示任务 & 20 & 0.51 & 已登记 \\
\bottomrule
\end{tabular}
\end{table}
'''
 s+=paragraphs([2,3])+r'\section{追溯信息}'+'\n'
 token='SyntheticCalibrationSequenceIdentifierForDemonstratingUnbreakableTextAcrossTheWholeLineWithoutChangingAnyRecordedContent'
 s+='下面的编号用于演示不可断长词的排版问题，优化时只能增加可选断词点，不能删改编号：\n\n'+token+'。\n\n'
 s+='下面的链接是明确的演示地址，不是真实数据仓库：\n\n'+r'\url{https://example.org/synthetic-layout-demonstration/archive/windows/structured-comparison/reporting/abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz0123456789}'+'\n\n'
 s+=paragraphs([4])+r'\vspace{24mm}'+'\n\n'
 s+=r'''\begin{itemize}[itemsep=20pt,topsep=20pt]
\item 表格应在版心内换行，而不是把文字缩到难以阅读。
\item 长链接应保持原文，允许排版引擎选择断行位置。
\item 所有内容改动检查都应以冻结的原稿为基准。
\end{itemize}
\section{结果说明}
'''+paragraphs([5,6,7])+r'\end{document}'+'\n'
 return s

OUT.mkdir(exist_ok=True)
for key,build in zip(CASES,[case1,case2,case3]):
 d=OUT/key;d.mkdir(exist_ok=True);src=d/'原始源码'
 if src.exists():raise FileExistsError('不覆盖已冻结的合成原稿：'+str(src))
 (src/'figs').mkdir(parents=True)
 asset(src/'figs/flow.pdf','处理流程','flow');asset(src/'figs/curves.pdf','人工构造的记录曲线','curve')
 text=build();(src/'main.tex').write_text(text,encoding='utf-8')
 hashes={p.relative_to(src).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file()}
 metadata={'synthetic':True,'not_a_published_paper':True,'generator':'workbench/synthetic_showcase/build_originals.py',
   'case':key,'title':CASES[key]['title'],'deliberate_layout_defects':CASES[key]['focus'],
   'frozen_original_hashes':hashes,'content_policy':'生成后冻结；修复只允许白名单排版操作，正文、数值、公式和原图文件不改。'}
 (d/'合成来源与原稿清单.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'case':key,'synthetic':True,'source_files':len(hashes),'characters':len(text)},ensure_ascii=False))
