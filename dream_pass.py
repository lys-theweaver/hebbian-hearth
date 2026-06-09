#!/usr/bin/env python3
"""
hebbian-hearth · dream_pass.py — 每晚做一次梦
1. 衰减：所有突触 weight x 0.95（遗忘曲线）
2. 修剪：weight < 0.1 的线剪掉
3. 发现：语义相近但还没连过的记忆对，每晚牵最多10根新线
4. 热度：所有记忆 heat x 0.97（地板0.05）
建议 cron：0 20 * * *  (UTC，即北京时间凌晨4点)
"""
import os, json, urllib.request
from datetime import datetime, timedelta, timezone

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_env()
SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_KEY"]
H = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

def rpc(sql):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/exec_sql",
        data=json.dumps({"query": sql}).encode(), headers=H, method="POST")
    try: return json.loads(urllib.request.urlopen(req).read())
    except Exception as e: print("rpc err:", e); return None

def count(table):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?select=id",
        headers={**H, "Prefer": "count=exact", "Range": "0-0"})
    try:
        cr = urllib.request.urlopen(req).headers.get("Content-Range", "/0")
        return int(cr.split("/")[-1])
    except: return 0

def query(table, params=""):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{params}", headers=H)
    try: return json.loads(urllib.request.urlopen(req).read())
    except: return []

def dream():
    print("=== 开始做梦 ===\n")
    before = count("synapses")

    rpc("UPDATE synapses SET weight = weight * 0.95, updated_at = now()")
    print(f"[衰减] 所有连接 x0.95 ({before}根线)")

    rpc("DELETE FROM synapses WHERE weight < 0.1")
    after = count("synapses")
    print(f"[修剪] 断掉 {before - after} 根弱线, 剩余 {after}")

    # 语义发现：相似度>0.45、还没连过的记忆对，取最像的10对，初始weight=相似度x0.6
    rpc("""
    INSERT INTO synapses (source_id, target_id, weight)
    SELECT a.id, b.id, ROUND((1-(a.embedding <=> b.embedding))::numeric * 0.6, 2)
    FROM memories a, memories b
    WHERE a.id < b.id
      AND a.embedding IS NOT NULL AND b.embedding IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM synapses s
        WHERE (s.source_id=a.id AND s.target_id=b.id)
           OR (s.source_id=b.id AND s.target_id=a.id))
      AND 1-(a.embedding <=> b.embedding) > 0.45
    ORDER BY 1-(a.embedding <=> b.embedding) DESC
    LIMIT 10
    ON CONFLICT (source_id, target_id) DO NOTHING
    """)
    final = count("synapses")
    print(f"[发现] 新连 {final - after} 对, 总计 {final} 根线")

    # 报告：最近25小时的新线，配上两端记忆的摘要
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S")
    links = query("synapses", f"select=source_id,target_id,weight&created_at=gte.{cutoff}&order=created_at.desc&limit=15")
    ids = {str(l[k]) for l in links for k in ("source_id", "target_id")}
    mmap = {m["id"]: m["summary"] for m in (query("memories", f"select=id,summary&id=in.({','.join(ids)})") if ids else [])}
    enriched = []
    for l in links:
        e = {"from": mmap.get(l["source_id"], "?"), "to": mmap.get(l["target_id"], "?"), "weight": l["weight"]}
        enriched.append(e)
        print(f"  >> {e['from'][:30]} <-> {e['to'][:30]} ({e['weight']})")

    rpc("UPDATE memories SET heat = GREATEST(0.05, heat * 0.97) WHERE heat > 0.05")

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "dream_latest.json"), "w") as f:
        json.dump({"timestamp": datetime.now(timezone.utc).isoformat(),
                   "before": before, "pruned": before - after,
                   "discovered": final - after, "total": final,
                   "new_links": enriched}, f, ensure_ascii=False, indent=2)
    print("\n=== 醒了 ===")

if __name__ == "__main__":
    dream()
