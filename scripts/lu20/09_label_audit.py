import sys, json, importlib.util as iu, numpy as np, pandas as pd, geopandas as gpd, warnings
warnings.filterwarnings("ignore")
R=r"C:/Users/nisha/Desktop/CEProjNE"
sys.path[:0]=[R+"/scripts/lu20",R+"/scripts/lu"]
from common20 import *
from pyproj import Transformer
p=pd.read_csv(R+"/outputs/lu20/esri_check/handlabel_points.csv")
print("esri_2023 values:",sorted(p.esri_2023.dropna().unique()),"ours:",sorted(p.ours_2023.unique()))
x,y=Transformer.from_crs(4326,32644,always_xy=True).transform(p.lon.values,p.lat.values)
s=iu.spec_from_file_location("eh",R+"/scripts/lu/07_eval_handlabels.py"); eh=iu.module_from_spec(s); s.loader.exec_module(eh)
dw=pd.Series(eh.read_at("prod",1,x,y)).map({0:"water",1:"trees",2:"open",3:"open",4:"open",5:"open",6:"built",7:"open",8:"open"})
wc=pd.Series(eh.read_at("prod",2,x,y)).map({10:"trees",20:"open",30:"open",40:"open",50:"built",60:"open",70:"open",80:"water",90:"open",95:"trees",100:"open"})
to4={1:"built",2:"built",3:"water",4:"trees",5:"open"}
meta=json.loads((W20/"grid_2023"/"meta.json").read_text())
r=((meta["maxy"]-y)//20).astype(int); c=((x-meta["minx"])//20).astype(int)
es=np.load(W20/"ext"/"esri_2023.npz"); b,w,t=es["built"][r,c],es["water"][r,c],es["trees"][r,c]
esri=pd.Series(np.array(["built","water","trees","open"])[np.argmax(np.stack([b,w,t,100-b-w-t]),0)])
wsf=pd.Series(np.where(np.load(W20/"ext"/"wsf_2019.npz")["built"][r,c]>=50,"built","notbuilt"))
h=p.true_class.map(to4); o=p.ours_2023.map(to4)
print("\nagreement of your labels with each map (313 points, 4 classes, unweighted):")
for n,m in (("ours",o),("Esri 2023",esri),("WorldCover",wc),("Dynamic World",dw)): print(f"  {n}: {(h.values==m.values).mean():.3f}")
print("\ncases where you and our model disagree (4 classes):")
dis=(h.values!=o.values); print("  n =",dis.sum())
wit={"Esri":esri,"WorldCover":wc,"DW":dw}
rows=[]
for i in np.nonzero(dis)[0]:
    v=[m.iloc[i] for m in wit.values()]
    rows.append({"you":h[i],"ours":o[i],"for_you":sum(a==h[i] for a in v),"for_ours":sum(a==o[i] for a in v),"conf":p.confidence[i],"st":p.stratum[i]})
d=pd.DataFrame(rows)
d["side"]=np.where(d.for_you>d.for_ours,"witnesses back YOU",np.where(d.for_ours>d.for_you,"witnesses back MODEL","split"))
print(d.side.value_counts().to_string())
print(pd.crosstab([d.you,d.ours],d.side).to_string())
print("\nall 3 witnesses against you, for every point (not only disagreements):")
v=pd.DataFrame(wit); allag=(v.nunique(axis=1)==1)&(v.iloc[:,0].values!=h.values)
print("  n =",allag.sum()); print(pd.crosstab(h[allag],v.iloc[:,0][allag]).to_string())
print("\nmodel match by your confidence:"); 
print(pd.DataFrame({"conf":p.confidence,"m":h.values==o.values,"m5":p.true_class.values==p.ours_2023.values}).groupby("conf").agg(n=("m","size"),match_4class=("m","mean"),match_5class=("m5","mean")).round(3).to_string())
# OSM 2023 polygons
g=gpd.read_file(PROC/"lu20"/"osm_2023"/"geofabrik.gpkg")[["landuse","amenity","office","shop","building","geometry"]].to_crs(32644)
RES={"residential"}; NR={"industrial","commercial","retail","education","civic"}
g["osm"]=np.select([g.landuse.isin(NR)|g.office.notna()|g.amenity.notna()|g.shop.notna(),g.landuse.isin(RES)|g.building.isin(["residential","house","apartments"])],["nonres","res"],"")
g=g[g.osm!=""]
pts=gpd.GeoDataFrame({"i":range(len(p))},geometry=gpd.points_from_xy(x,y),crs=32644)
j=gpd.sjoin(pts,g[["osm","geometry"]],how="inner",predicate="within").sort_values("osm").drop_duplicates("i")
tmp=pd.DataFrame({"you":p.true_class.iloc[j.i].map({1:"res",2:"nonres",3:"water",4:"trees",5:"open"}).values,"osm":j.osm.values,"ours":p.ours_2023.iloc[j.i].map({1:"res",2:"nonres",3:"water",4:"trees",5:"open"}).values})
print("\npoints inside OSM 2023 use polygons, your label vs OSM:"); print(pd.crosstab(tmp.osm,tmp.you).to_string())
print("same points, our model vs OSM:"); print(pd.crosstab(tmp.osm,tmp.ours).to_string())

# ---- how much could the headline move if the suspect labels were wrong?
W=pd.read_csv(LUP/"validation_strata.csv",index_col=0)["weight"].to_dict()
def score(ref,pred,st):
    k=pred>0; ref,pred,st=ref[k],pred[k],st[k]; P=np.zeros((5,5))
    for hh,w_ in W.items():
        m=st==hh
        if m.sum(): P+=w_*np.bincount((pred[m]-1)*5+(ref[m]-1),minlength=25).reshape(5,5)/m.sum()
    ua=np.divide(np.diag(P),P.sum(1),out=np.zeros(5),where=P.sum(1)>0); pa=np.divide(np.diag(P),P.sum(0),out=np.zeros(5),where=P.sum(0)>0)
    f=np.divide(2*ua*pa,ua+pa,out=np.zeros(5),where=(ua+pa)>0); return f.mean(),f[0],f[1],ua[1],pa[1]
ref=p.true_class.values.copy(); pred=p.ours_2023.values; st=p.stratum.values
inosm=pd.Series(False,index=p.index); osmnr=j[j.osm=="nonres"].i.values; inosm.iloc[osmnr]=True
A=inosm.values&np.isin(ref,[4,5])                          # your open/trees inside OSM non-res polygons
B=allag.values&(h.values=="open")&(v.iloc[:,0].values=="built")   # you open; Esri, WC, DW all built
C=dis&(d.side.reindex(range(len(d))).values is not None)
rows=[("as labelled",ref)]
r1=ref.copy(); r1[A]=2; rows.append((f"A: {A.sum()} open/trees inside OSM non-res polygons become non-res",r1))
r2=ref.copy(); r2[B]=pred[B]; rows.append((f"B: {B.sum()} open where all 3 maps say built take the model's class",r2))
r3=r1.copy(); r3[B]=pred[B]; rows.append(("A + B (best case for the model)",r3))
print("\n5-class score, year_2023 map (stratum weighted):")
for n,rr in rows:
    s_=score(rr,pred,st); print(f"  {n}: macro-F1 {s_[0]:.3f} | res F1 {s_[1]:.3f} | non-res F1 {s_[2]:.3f} (precision {s_[3]:.2f}, recall {s_[4]:.2f})")
out=p[["pid","lat","lon","true_class","confidence","is_road","stratum","ours_2023"]].copy()
out["esri_2023"]=esri; out["worldcover"]=wc.values; out["dynamic_world"]=dw.values
out["reason"]=np.where(A&B,"inside OSM non-res; all 3 maps built",np.where(A,"inside OSM non-res polygon",np.where(B,"all 3 maps say built",np.where(allag.values,"all 3 maps disagree","")))) 
out["google_maps"]="https://www.google.com/maps/@"+out.lat.round(6).astype(str)+","+out.lon.round(6).astype(str)+",150m/data=!3m1!1e3"
sus=out[out.reason!=""].sort_values("reason")
D=Path(R)/"outputs/lu20/label_audit"; D.mkdir(exist_ok=True); sus.to_csv(D/"points_to_look_at.csv",index=False)
print("\nexported",len(sus),"points"); print(sus.reason.value_counts().to_string())
