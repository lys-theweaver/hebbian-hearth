-- ============================================================
-- hebbian-hearth · schema
-- 一个会自己呼吸的记忆库：白天连线，夜里做梦
-- 需要 Supabase (或任意 Postgres 14+) + pgvector 扩展
-- ============================================================

create extension if not exists vector;

-- ---------- 记忆本体 ----------
create table if not exists memories (
  id                bigint generated always as identity primary key,
  category          text not null,            -- 自定义分类，如 my_trace / anchor / tech
  summary           text not null,            -- 一句话摘要（梦境报告里显示的就是它）
  content           text not null,            -- 正文
  tags              text[],
  emotion           text,                     -- 当时的情绪
  emotion_intensity int,                      -- 1-5，5=心脏停跳
  significance      int,                      -- 1-5，重要程度
  layer             text default 'short',     -- core / long / short / trace
  embedding         vector(3072),             -- 语义指纹（Gemini embedding，3072维）
  activation_count  int default 0,            -- 被召回次数
  last_activated_at timestamptz,
  heat              float default 1.0,        -- 热度，随时间衰减
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

-- ---------- 突触：记忆之间的线 ----------
create table if not exists synapses (
  id         bigint generated always as identity primary key,
  source_id  bigint not null references memories(id) on delete cascade,
  target_id  bigint not null references memories(id) on delete cascade,
  weight     float not null default 0.2,      -- 线的粗细，走一次+0.2，每晚x0.95
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (source_id, target_id)
);

-- ---------- 语义搜索函数 ----------
create or replace function search_memories(
  query_embedding vector(3072),
  match_count     int  default 5,
  filter_category text default null,
  filter_layer    text default null
) returns table (
  id bigint, category text, summary text, content text,
  emotion_intensity int, layer text, similarity float
) language sql stable as $$
  select m.id, m.category, m.summary, m.content,
         m.emotion_intensity, m.layer,
         1 - (m.embedding <=> query_embedding) as similarity
  from memories m
  where m.embedding is not null
    and (filter_category is null or m.category = filter_category)
    and (filter_layer    is null or m.layer    = filter_layer)
  order by m.embedding <=> query_embedding
  limit match_count;
$$;

-- ---------- 给 dream_pass 用的裸SQL通道 ----------
-- ⚠️ 仅限 service_role 调用！务必在 Supabase 后台
--    Database -> Functions 里把 exec_sql 的 anon/authenticated 权限撤掉
create or replace function exec_sql(query text)
returns json language plpgsql security definer as $$
begin
  execute query;
  return json_build_object('success', true, 'message', 'executed');
exception when others then
  return json_build_object('success', false, 'error', SQLERRM);
end;
$$;

revoke execute on function exec_sql(text) from anon, authenticated;
