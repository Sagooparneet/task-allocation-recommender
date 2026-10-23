from html import escape
from IPython.display import HTML, display
from .preprocessing import ROOT

def table(rows):
    if not rows:
        return
    columns=list(dict.fromkeys(key for row in rows for key in row))
    html='<table><tr>'+''.join('<th>'+escape(str(c))+'</th>' for c in columns)+'</tr>'
    for row in rows:
        html+='<tr>'+''.join('<td>'+escape(str(row.get(c,'')))+'</td>' for c in columns)+'</tr>'
    display(HTML(html+'</table>'))

def metric_row(name,m):
    return {'Model':name,**{label:round(100*m[key],3) for label,key in {
        'Top-1 %':'top1_success','P@3 %':'precision_at_k','R@3 %':'recall_at_k',
        'MAP@3 %':'map_at_k','Full MAP %':'map','NDCG@3 %':'ndcg_at_k'}.items()}}

def chart(name,metric,filename):
    import matplotlib.pyplot as plt
    keys=['top1_success','precision_at_k','recall_at_k','map_at_k','ndcg_at_k']
    fig,ax=plt.subplots(figsize=(9,4))
    bars=ax.bar(['Top-1','P@3','R@3','MAP@3','NDCG@3'],[100*metric[k] for k in keys],color='#0f766e')
    ax.bar_label(bars,fmt='%.2f%%',padding=3); ax.set(ylim=(0,110),ylabel='Percent',title=name)
    fig.tight_layout(); (ROOT/'reports/figures').mkdir(exist_ok=True)
    fig.savefig(ROOT/'reports/figures'/filename,dpi=160); plt.show()
