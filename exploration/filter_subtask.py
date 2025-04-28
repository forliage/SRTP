# 第一批subtask可以这样分类，首先是全部300+subtask
# 然后可以分为有成功轨迹的subtask（255）以及有交叉验证通过的subtask（205）
# 前者可以用来训练但测试时评估函数可能有错误，后者可以用来测试同时轨迹大概率也是正确的所以可以拿来训练
# 这里主表用的二者交集（165）组合出来的DAG，为了尽量好看一些
import json
import os

# 检查第一部分[subtask1-2]filtered_logs目录
path1 = "D:/data/[subtask1-2]filtered_logs"
cnt1 = 0
filtered1 = []
subtask_ids = set() # 用于记录已处理的subtask id

for root, dirs, files in os.walk(path1):
    for dir in dirs:
        # 提取subtask id (去掉括号后的数字)
        dir = os.path.basename(dir)
        subtask_id = dir.split('(')[0] if '(' in dir else dir
        
        if subtask_id not in subtask_ids and os.path.exists(os.path.join(root, dir, "eval_history.txt")):
            eval_res = json.load(open(os.path.join(root, dir, "eval_history.txt"), 'r'))
            if "success" in eval_res[-1] or "discriminative" in eval_res[-1]:
                cnt1 += 1
                subtask_ids.add(subtask_id)
            else:
                filtered1.append(os.path.join(root, dir))

print(f"[subtask1-2]filtered_logs目录下保留的subtask数量: {cnt1}")
print("被过滤掉的subtask路径:")
# for path in filtered1:
#     print(path)

# 检查第二部分[subtask3-4]filtered_logs目录
path2 = "D:/data/[subtask3-4]filtered_logs"
cnt2 = 0 
filtered2 = []
# subtask_ids.clear() # 清空set重新统计第二部分

for root, dirs, files in os.walk(path2):
    for dir in dirs:
        dir = os.path.basename(dir)
        subtask_id = dir.split('(')[0] if '(' in dir else dir
        
        if subtask_id not in subtask_ids and os.path.exists(os.path.join(root, dir, "eval_history.txt")):
            eval_res = json.load(open(os.path.join(root, dir, "eval_history.txt"), 'r'))
            if "success" in eval_res[-1] or "discriminative" in eval_res[-1]:
                cnt2 += 1
                subtask_ids.add(subtask_id)
            else:
                filtered2.append(os.path.join(root, dir))

print(f"\n[subtask3-4]filtered_logs目录下保留的subtask数量: {cnt2}")
print("被过滤掉的subtask路径:")
# for path in filtered2:
#     print(path)

print(f"\n总共保留的subtask数量: {cnt1 + cnt2}")
print(f"总共被过滤掉的subtask数量: {len(filtered1) + len(filtered2)}")

# print(subtask_ids)

# 看255个有成功轨迹的看看交集
with open("D:/data/succ_subtask_trajs.json", "r", encoding="utf-8") as f:
    t = json.load(f)
tt = []
for i in t:
    tt.append(i[:-3])

# print(set(tt) & subtask_ids)

# with open("D:/data/succ_subtask_evals.json", "w", encoding="utf-8") as f:
#     json.dump(list(subtask_ids), f, indent=4)

ttt = list(set(tt) & subtask_ids)
with open("D:/data/succ_subtask_both.json", "w", encoding="utf-8") as f:
    json.dump(ttt, f, indent=4)
