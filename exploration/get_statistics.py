# 统计需要联网的app
import os
import json

online_app = ["Microsoft Edge", "Google Chrome", "TuneIn", "BreeZip", "Adobe Photoshop Express", "DeepL", "Wikipedia", "Microsoft Clipchamp", "Maps", "Microsoft Store"]

json_folder = r"D:\data\[explicit_app]task_DAG_batch1"
json_files = []

with open('D:/data/all_task.json', 'r') as f:
    subtasks = json.load(f)
    subtask_map = {subtask['id']: subtask for subtask in subtasks}

# Walk through the directory
for root, dirs, files in os.walk(json_folder):
    for file in files:
        if file.endswith('.json') and os.path.basename(file)[:-5].isdigit():
            json_path = os.path.join(root, file)
            json_files.append(json_path)

# Now json_files contains paths to all JSON files in the directory
ecnt = 0
cnt = 0
all_apps = set()
error_files = []
for json_file in json_files:
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # print(data["dag"]["nodes"])
            nodes = data["dag"]["nodes"]
            flag = False
            for node in nodes:
                all_apps.add(subtask_map[node]["application"])
            for node in nodes:
                if subtask_map[node]["application"] in online_app:
                    flag = True
                    cnt += 1
                    break
    except Exception as e:
        ecnt += 1
        error_files.append(json_file)
        print(f"Error processing {json_file}: {str(e)}")
# print(len(json_files))
print(ecnt, cnt)
print(all_apps)
print(len(json_files))
print(error_files)