"""Study workflow. Code Apache-2.0; original figure CC-BY-4.0.
Copyright 2026 Rongrong Li and Jiecai Zheng. No statistical recomputation.
"""
from pathlib import Path
import argparse
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7.5,'svg.fonttype':'none','pdf.fonttype':42})
NAVY='#122F49';BLUE='#09AAD0';LINE='#54748C';PALE='#EFF7FB';TEAL='#EAF6F4';GOLD='#FFF6E5'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=Path(__file__).parent/'generated');args=ap.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
 fig=plt.figure(figsize=(7.028,5.784),facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(.22,17.79),ylim=(.92,15.38));ax.set_aspect('equal');ax.axis('off')
 def text(x,y,s,size=7.5,bold=False,ha='left',color=NAVY):
  ax.text(x,y,s,fontsize=size,fontweight='bold' if bold else 'normal',ha=ha,va='center',color=color,linespacing=1.35)
 def rect(x,y,w,h,fill='white',edge='#BED2DF',r=.12):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',facecolor=fill,edgecolor=edge,linewidth=.8))
 def arrow(a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=9,linewidth=1.1,color=LINE,shrinkA=2,shrinkB=2))
 def panel(x,y,n,title,fill):rect(x,y,5.45,6.65,fill);text(x+.23,y+6.22,f'{n}  {title}',9,True)
 def doc(x,y):
  ax.add_patch(Rectangle((x,y),.58,.77,facecolor='white',edgecolor=LINE,linewidth=.85))
  for dy in [.18,.36,.54]:ax.plot([x+.12,x+.46],[y+dy]*2,color='#8CA8BB',lw=.8)
 def robot(x,y):
  rect(x,y,.72,.62,BLUE,BLUE,.08)
  for dx in [.20,.52]:ax.add_patch(Circle((x+dx,y+.34),.085,facecolor='white',edgecolor=NAVY,lw=.65))
  for dx in [.2,.52]:ax.plot([x+dx]*2,[y+.65,y+.82],color=BLUE,lw=1.8,solid_capstyle='round')
 def human(x,y):ax.add_patch(Circle((x,y+.45),.16,facecolor='white',edgecolor=LINE,lw=1));rect(x-.28,y-.03,.56,.28,'white',LINE,.1)
 def pill(x,y,w,label,fill='white',size=7.5):rect(x,y,w,.55,fill);text(x+w/2,y+.275,label,size,ha='center')
 xs=[.3,6.28,12.26];top=8.65;bottom=1
 for x,n,title in zip(xs,'abc',['Dataset preparation','Experimental execution','Post-experiment processing']):panel(x,top,n,title,PALE)
 panel(xs[2],bottom,'d','Human audit',GOLD);panel(xs[1],bottom,'e','Audit-result integration',TEAL);panel(xs[0],bottom,'f','Statistical summaries',TEAL)
 for x in [5.75,11.73]:arrow((x,12),(x+.53,12))
 arrow((14.98,8.60),(14.98,7.69))
 for x in [12.22,6.24]:arrow((x,4.38),(x-.53,4.38))
 x=xs[0];doc(x+.3,13.55);doc(x+2.85,13.55)
 text(x+1.05,14.02,'2Wiki',8,True);text(x+1.05,13.61,'400 questions',7);text(x+3.60,14.02,'MuSiQue',8,True);text(x+3.60,13.61,'200 questions',7)
 arrow((x+2.72,13.4),(x+2.72,12.99));pill(x+.3,12.35,4.85,'GPT silver annotations');arrow((x+2.72,12.33),(x+2.72,11.92))
 human(x+.65,11.34);text(x+1.2,11.65,'Input review and correction',7.5,True);text(x+1.2,11.17,'Question–answer consistency\nClaim fidelity and source support',7)
 arrow((x+2.72,10.78),(x+2.72,10.42));pill(x+.3,9.77,4.85,'Eligible pools: 400 / 167',TEAL);text(x+2.72,9.20,'Experimental panels: 40 / 20',8,True,ha='center')
 x=xs[1]
 for j in range(3):
  robot(x+.67+j*1.58,13.65);text(x+1.03+j*1.58,13.25,f'Agent {j+1}',7,True,ha='center')
  if j<2:arrow((x+1.42+j*1.58,13.96),(x+2.20+j*1.58,13.96))
 text(x+2.72,12.77,'M: three-agent, single-round chain',7.3,ha='center');pill(x+.3,11.86,4.85,'B0 centralized  |  B1 independent');pill(x+.3,11.10,4.85,'A1 source masking  |  A2 no maintenance',size=6.8)
 text(x+.3,10.43,'2Wiki: 5 conditions × 40 × 2 runs\nMuSiQue: 3 conditions × 20 × 2 runs',7.3);text(x+2.72,9.64,'520 primary DeepSeek runs',8.5,True,ha='center');text(x+2.72,9.10,'Separate chain comparison:\nearlier DeepSeek / Qwen',6.6,ha='center')
 x=xs[2];doc(x+.4,13.55);doc(x+1.12,13.55);text(x+2,14.02,'Freeze outputs and IDs',8,True);text(x+2,13.57,'Messages · citations\nDependencies',6.8)
 arrow((x+2.72,13.32),(x+2.72,12.91));pill(x+.3,12.27,4.85,'Align claims and resolve source references',size=7);arrow((x+2.72,12.24),(x+2.72,11.83))
 for j,s in enumerate(['Nodes','Edges','Terminals']):pill(x+.30+j*1.64,11.16,1.55,s,TEAL)
 text(x+2.72,10.56,'Separate scopes and applicable events',7.2,ha='center');arrow((x+2.72,10.23),(x+2.72,9.92));pill(x+.3,9.20,4.85,'Candidate judgments + evidence ledgers',GOLD,7)
 x=xs[2];human(x+.66,6.10);text(x+1.22,6.42,'Route by evidence\nand complexity',7.3,True);text(x+1.22,5.78,'Non-blind, candidate-assisted review',6.8)
 for j,(a,b) in enumerate([('Identical evidence','Reuse prior human judgment'),('Complex evidence','Individual human review'),('Residual simple cases','Stratified sampled review')]):
  y=4.60-j*1.08;rect(x+.3,y,4.85,.86,'white','#E4C48B');text(x+.48,y+.58,a,7.5,True);text(x+.48,y+.23,b,7)
 text(x+2.72,1.49,'Review explanations → adjudication',7.5,True,ha='center')
 x=xs[1];text(x+2.72,6.38,'Terminal audit frame',8,True,ha='center');rect(x+.3,4.88,2.31,.94,'white');rect(x+2.84,4.88,2.31,.94,'white')
 text(x+1.455,5.51,'330 scopes',8,True,ha='center');text(x+1.455,5.14,'Reviewed or reused',6.8,ha='center');text(x+3.995,5.51,'1,036 scopes',8,True,ha='center');text(x+3.995,5.14,'Candidate-only',6.8,ha='center')
 arrow((x+1.455,4.85),(x+1.455,4.36));arrow((x+3.995,4.85),(x+3.995,4.36));pill(x+.3,3.66,2.31,'Human judgments',TEAL,7);pill(x+2.84,3.66,2.31,'Retain candidates',GOLD,7)
 arrow((x+1.455,3.63),(x+2.42,3.01));arrow((x+3.995,3.63),(x+3.03,3.01));pill(x+.3,2.36,4.85,'Audit-updated candidate view',size=7.5);text(x+2.72,1.57,'Preserve adjudications, versions\nand provenance',6.9,ha='center')
 x=xs[0];text(x+.3,6.31,'Nodes and terminals',8,True);text(x+.3,5.65,'Run-level rate → within-question mean\n→ equal mean across questions',7.4);text(x+.3,4.77,'Applicable edges',8,True);text(x+.3,4.22,'Pool positive / applicable event counts',7.3)
 for j,s in enumerate(['CSR','ESS','VSSR','AA']):pill(x+.3+j*1.23,3.16,1.14,s,'white',8)
 text(x+2.72,2.52,'Tables and figures',8,True,ha='center');text(x+2.72,1.66,'Supplementary: HT and difference estimates\nKeep audit uncertainty separate',7,ha='center')
 fig.savefig(out/'Figure_2.svg',facecolor='white');fig.savefig(out/'Figure_2.pdf',facecolor='white');fig.savefig(out/'Figure_2.png',dpi=600,facecolor='white')
 fig.savefig(out/'Figure_2.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'});fig.savefig(out/'Figure_2_preview.png',dpi=300,facecolor='white');plt.close(fig)
if __name__=='__main__':main()
