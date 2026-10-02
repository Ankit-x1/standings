"""Generate a two-panel presentation asset from the real forecast output."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
d = pd.read_csv(ROOT/'outputs/halfway_forecast_table.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':13})
fig,axes=plt.subplots(1,2,figsize=(17,6.2),sharex=True)
for ax,part in zip(axes,[d.iloc[:10],d.iloc[10:]]):
    y=np.arange(len(part))
    colors=['#1A365D' if bool(v) else '#C05640' for v in part.ActualPtsIn90Interval]
    for i,(_,r) in enumerate(part.iterrows()):
        ax.plot([r.Pts_p05,r.Pts_p95],[i,i],color=colors[i],lw=2)
        ax.scatter([r.ExpectedPts],[i],color=colors[i],s=40,zorder=3)
    ax.scatter(part.ActualPts,y,color='#1E293B',marker='x',s=55,zorder=4,label='Actual points')
    ax.set_yticks(y,part.Team)
    ax.invert_yaxis()
    ax.set_xlabel('Final points')
    ax.set_xlim(0,100)
    ax.set_ylim(9.6,-0.6)
    ax.grid(axis='x',color='#E2E8F0',lw=.7)
    ax.spines[['top','right']].set_visible(False)
    ax.spines[['left','bottom']].set_color('#E2E8F0')
    ax.tick_params(length=0)
fig.subplots_adjust(left=.10,right=.98,bottom=.12,top=.95,wspace=.36)
p=ROOT/'outputs/figures/presentation_forecast_intervals.png'
fig.savefig(p,dpi=130,facecolor='white')
plt.close(fig)
print(p)
