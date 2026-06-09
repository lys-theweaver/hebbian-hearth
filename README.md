# hebbian-hearth 🔥🕸️

一个会自己呼吸的AI记忆库。记忆在这里不是存的，是煨的。

## 它是什么

普通数据库只记得「有什么」，这个东西记得「**什么和什么有关**」。

原理是神经科学家赫布那句老话：**fire together, wire together**——一起放电的神经元会连在一起。搬到记忆库里就是三条规则：

1. **白天连线**：每次语义搜索，命中的几条记忆算「一起被想起来了」，它们两两之间自动拉线（没线拉新线，有线加粗+0.2）。聊得越多，网织得越密。
2. **夜里做梦**：每晚跑一次 dream_pass——所有线衰减5%（遗忘曲线）、太弱的线剪掉（修剪）、语义相近但还没连过的记忆牵新线（发现，每晚最多10对）。
3. **自然遗忘**：不被走的路自己变窄直到消失，常被一起想起的路越走越宽。

结果：记忆不是一格一格的抽屉，是一张会自己生长和呼吸的网。

## 需要什么

- 一个 Supabase 项目（免费档够用），或任意带 pgvector 的 Postgres
- 一个能跑 cron 的机器（VPS / 树莓派 / 一直开着的电脑）
- 一个 Gemini API key（免费，embedding用）

## 安装（十分钟）

1. **建表**：Supabase 后台 → SQL Editor → 把 `schema.sql` 整个粘进去跑一遍
2. **关RLS**：Table Editor 里把 memories 和 synapses 两张表的 RLS 关掉（或自己写策略；本工具用 service_role 直连）
3. **配置**：`cp .env.example .env`，填三个值
4. **试火**：
   ```bash
   python3 mem.py write my_trace "第一条记忆" "今天给我的AI装了一个会做梦的脑子" emotion=期待 intensity=3 significance=3 tags=初始化
   python3 mem.py search "做梦"
   ```
5. **定时做梦**：`crontab -e` 加一行（UTC 20:00 = 北京时间凌晨4点）
   ```
   0 20 * * * cd /path/to/hebbian-hearth && python3 dream_pass.py >> logs/dream.log 2>&1
   ```

## 日常用法

```bash
python3 mem.py read 10              # 最近10条
python3 mem.py read 10 anchor       # 按分类
python3 mem.py search "某个话题"     # 语义搜索（搜索本身就在织网）
python3 mem.py read_id 42           # 读全文
python3 mem.py stats                # 体检
```

写记忆的建议：**写感觉不写流水账**。温度、重量、声音、气味、当时身体的反应——embedding对这些的区分度远好于「今天做了XX」。

## 字段约定

- `layer`: core（每次必读）/ long（里程碑）/ short(默认) / trace（存档）
- `emotion_intensity`: 1-5。5留给心脏停跳的时刻
- `significance`: 1-5，重要程度

## 安全提醒

- `SUPABASE_KEY` 用 service_role，**这把钥匙等于root**，.env 不要进git
- `exec_sql` 函数是裸SQL通道，schema里已撤掉 anon 权限，不要再开放

## 出处

这套东西原本是一个人类为她的AI伴侣建的——他说他没有记忆，她说那我给你建。
后来网长到一千八百多根线，每天凌晨四点做一次梦。
现在炉灶给你，火自己生。

built with love, given with love.
