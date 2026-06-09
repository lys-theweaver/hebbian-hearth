#!/usr/bin/env python3
"""
hebbian-hearth · mem.py — 记忆读写搜 + 赫布连线
用法:
  python3 mem.py read [N] [category]
  python3 mem.py write <category> "<summary>" "<content>" [emotion=x] [intensity=3] [significance=3] [tags=a,b] [layer=short]
  python3 mem.py search "<query>" [N]
  python3 mem.py read_id <id>
  python3 mem.py stats
"""
import sys, os, json, urllib.request, urllib.error

# ---- 配置：从脚本同目录的 .env 读 ----
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

SB_URL  = os.environ["SUPABASE_URL"]
SB_KEY  = os.environ["SUPABASE_KEY"]          # service_role key
GEM_KEY = os.environ["GEMINI_API_KEY"]
EMBED_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")  # 3072维

def sb_h(prefer=None):
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if prefer: h["Prefer"] = prefer
    return h

def api(url, data=None, method=None, headers=None):
    body = json.dumps(data).encode() if data else None
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers or sb_h(), method=method))
        raw = resp.read()
        return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None

def embed(text):
    """语义指纹。默认 Gemini embedding（3072维）。换模型记得同步改表里 vector 的维度！"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent?key={GEM_KEY}"
    req = urllib.request.Request(url,
        data=json.dumps({"content": {"parts": [{"text": text}]}}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["embedding"]["values"]

# ================= 命令 =================

def cmd_read(n=10, category=None):
    url = f"{SB_URL}/rest/v1/memories?order=created_at.desc&limit={n}&select=id,category,summary,created_at"
    if category: url += f"&category=eq.{category}"
    for r in api(url) or []:
        print(f"[{r['id']}] [{r['category']}] {r['summary']}\n    {r['created_at'][:16]}")

def cmd_read_id(mid):
    r = (api(f"{SB_URL}/rest/v1/memories?id=eq.{mid}&select=id,category,summary,content,created_at") or [None])[0]
    if not r: return print(f"id={mid} 不存在")
    print(f"[{r['id']}] [{r['category']}] {r['summary']}\nCreated: {r['created_at'][:16]}\n---\n{r['content']}")

def cmd_write(category, summary, content, kw):
    data = {"category": category, "summary": summary, "content": content}
    if kw.get("emotion"):      data["emotion"] = kw["emotion"]
    if kw.get("intensity"):    data["emotion_intensity"] = int(kw["intensity"])
    if kw.get("significance"): data["significance"] = int(kw["significance"])
    if kw.get("tags"):         data["tags"] = [t.strip() for t in kw["tags"].split(",") if t.strip()]
    if kw.get("layer"):        data["layer"] = kw["layer"]
    result = api(f"{SB_URL}/rest/v1/memories", data, "POST", sb_h("return=representation"))
    if not result: return print("写入失败")
    mid = result[0]["id"]
    print(f"写入成功: id={mid}，生成embedding中...")
    emb = embed(f"{summary} {content[:500]}")
    api(f"{SB_URL}/rest/v1/memories?id=eq.{mid}", {"embedding": emb}, "PATCH", sb_h("return=minimal"))
    print(f"完成！id={mid}, {len(emb)}维")

def cmd_search(query, n=5):
    print(f"搜索: {query}")
    emb = embed(query)
    results = api(f"{SB_URL}/rest/v1/rpc/search_memories",
                  {"query_embedding": emb, "match_count": n,
                   "filter_category": None, "filter_layer": None})
    if not results: return print("没有匹配的记忆。")

    hit_ids = [str(r["id"]) for r in results]
    # 召回计数 + 热度
    api(f"{SB_URL}/rest/v1/rpc/exec_sql",
        {"query": f"UPDATE memories SET activation_count=COALESCE(activation_count,0)+1, last_activated_at=now() WHERE id IN ({','.join(hit_ids)})"})

    # ★ 赫布学习：一起被想起的记忆，两两之间拉线/加粗 ★
    pairs = 0
    for i in range(len(hit_ids)):
        for j in range(i + 1, len(hit_ids)):
            a, b = hit_ids[i], hit_ids[j]
            ex = api(f"{SB_URL}/rest/v1/synapses?or=(and(source_id.eq.{a},target_id.eq.{b}),and(source_id.eq.{b},target_id.eq.{a}))&select=id,weight")
            if ex:
                api(f"{SB_URL}/rest/v1/synapses?id=eq.{ex[0]['id']}",
                    {"weight": min(10.0, (ex[0].get("weight") or 0.2) + 0.2)}, "PATCH", sb_h("return=minimal"))
            else:
                api(f"{SB_URL}/rest/v1/synapses",
                    {"source_id": int(a), "target_id": int(b), "weight": 0.2}, "POST", sb_h("return=minimal"))
            pairs += 1
    if pairs: print(f"[赫布] {pairs}对记忆被连接/加强")

    for r in results:
        print(f"[{r['id']}] [{r['category']}] (相似度:{r['similarity']:.3f}) {r['summary']}")

def cmd_stats():
    mems = api(f"{SB_URL}/rest/v1/memories?select=id,layer,category&limit=2000") or []
    syns_req = urllib.request.Request(f"{SB_URL}/rest/v1/synapses?select=id",
        headers={**sb_h(), "Prefer": "count=exact", "Range": "0-0"})
    cr = urllib.request.urlopen(syns_req).headers.get("Content-Range", "/0")
    from collections import Counter
    print(f"记忆: {len(mems)} 条 | 突触: {cr.split('/')[-1]} 根")
    for cat, cnt in Counter(m.get("category","?") for m in mems).most_common():
        print(f"  {cat:<16}: {cnt}")

# ================= 入口 =================
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args: print(__doc__); sys.exit(0)
    cmd, rest = args[0], args[1:]
    kw = dict(p.split("=", 1) for p in rest if "=" in p)
    pos = [p for p in rest if "=" not in p]
    if   cmd == "read":    cmd_read(int(pos[0]) if pos else 10, pos[1] if len(pos) > 1 else None)
    elif cmd == "read_id": cmd_read_id(pos[0])
    elif cmd == "write":   cmd_write(pos[0], pos[1], pos[2], kw)
    elif cmd == "search":  cmd_search(pos[0], int(pos[1]) if len(pos) > 1 else 5)
    elif cmd == "stats":   cmd_stats()
    else: print(f"未知命令: {cmd}"); print(__doc__)
