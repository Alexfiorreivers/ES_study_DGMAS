"""Generate optional local charts from released CSVs; no statistical recomputation."""
from pathlib import Path
import argparse,csv,runpy

def main():
    here=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=here/'generated')
    args=parser.parse_args()
    # Validate the current aggregate release before drawing; no ledger rescan.
    runpy.run_path(str(here.parent/'results/current_release/validate_release_alignment.py'),run_name='__main__')
    OUT=args.output_dir.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tables=[]
    for number in range(2,7):
        with (here/'source_data'/f'Table_{number}.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=[row for row in csv.reader(f) if row]
        if rows[0][-4:]!=['CSR','ESS','VSSR','AA']:
            raise ValueError('Unexpected CSV metric columns')
        tables.append(rows)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':9,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7})
    for num,rows in enumerate(tables,2):
     labels=[r[0].replace(' / ',' ') for r in rows[1:]]
     if num==2:labels=['DeepSeek 1.0.4','DeepSeek earlier','Qwen3-8B']
     vals=[[float(v) for v in r[-4:]] for r in rows[1:]]
     fig,axs=plt.subplots(1,4,figsize=(6.48,2.18),sharey=True)
     fig.subplots_adjust(left=.20,right=.98,top=.83,bottom=.24,wspace=.28)
     for k,(ax,m) in enumerate(zip(axs,['CSR','ESS','VSSR','AA'])):
      ax.set_title(f'{chr(97+k)}  {m}',loc='left',fontweight='bold',pad=9)
      for j,(label,v) in enumerate(zip(labels,vals)):
       ax.plot(v[k],len(labels)-1-j,marker=['o','s','D'][j],markersize=5.8,color=['#356A91','#B98049','#718874'][j],linestyle='None')
      xmax=(6 if m=='VSSR' else 45) if num==2 else (15 if m=='VSSR' else 100)
      ax.set_xlim(-xmax*.04,xmax*1.04);ax.set_xticks([0,xmax/2,xmax]);ax.set_xlabel('Rate (%)')
      ax.set_ylim(-.5,len(labels)-.5);ax.set_yticks(range(len(labels)));ax.set_yticklabels(labels[::-1]);ax.tick_params(axis='y',length=0,pad=7)
      ax.grid(axis='x',color='#E3E5E8',linewidth=.6);ax.set_axisbelow(True)
     for ext in ['png','pdf','svg']:fig.savefig(OUT/f'Figure_{num+1}.{ext}',dpi=600,facecolor='white')
     plt.close(fig)
    print(f'Generated 15 local exports in {OUT}; no source data modified.')

if __name__=='__main__':main()
