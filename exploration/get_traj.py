# 需要自己设计action space，和web对应应该不错，但是android环境不好搞
# 轨迹中间步骤连接时需要
# 1.把subtask最后一步替换为Win+D (当下一个application在桌面上时)
# 2.把subtask最后一步删掉 (当下一个application在taskbar上时)
# 键盘输入应该需要转化，加一步click

# 先读入DAG看看有多少条topo轨迹，用全部的未语义一致的3w数据
import os
import json
from tqdm import tqdm
import concurrent.futures
import math

def extract_action(control_text, function, args):
    action = "no operation"
    if function == "click_input":
        times = "Double" if args['double'] else "Single"
        action = f"{times}-click the '{control_text}' with the {args['button']} mouse button."
    elif function == "Keyboard_input":
        keys = args['keys']
        keys = keys.replace("+", "SHIFT+")
        keys = keys.replace("^", "CTRL+") 
        keys = keys.replace("%", "ALT+")
        action = f"Input '{keys}' using the keyboard."
    elif function == "wheel_mouse_input":
        direction = "up" if args['wheel_dist'] > 0 else "down"
        dist = abs(args['wheel_dist'])
        action = f"Scroll the mouse wheel {direction} by {dist} distance."

    return action

def process_file(file_path, dic):
    messages = []
    with open(file_path, 'r', encoding='utf-8') as f:
        dag_data = json.load(f)
        if 'successful_topo' in dag_data:
            for topo in dag_data['successful_topo']:
                history_actions = []
                task_instruction = dag_data["task_instruction"]
                task_intent = dag_data["task_intent"]
                for j in topo:
                    obs = dic[j]["observations"]
                    act = dic[j]["actions"]
                    traj_len = len(obs)
                    for k in range(traj_len):
                        action = {k: v for k, v in act[k].items() if k != 'thought' or k != 'obs'}
                        action["rect"] = [action["rect"][0]*1000//1920, action["rect"][1]*1000//1080, action["rect"][2]*1000//1920, action["rect"][3]*1000//1080]
                        try:
                            obs_content = act[k]["obs"]
                            thought = act[k]["thought"]
                        except KeyError:
                            print(j)
                            assert False
                        m = {
                            "messages": [
                            {
                                "content": """You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of actions to complete the task. Each action contains three fields:
- function: The type of action ('click_input', 'keyboard_input', or 'wheel_mouse_input')
- args: The parameters for the action:
  • click_input args: {button: 'left'/'right'/'middle', double: true/false}
  • keyboard_input args: {keys: string for keyboard input with special formats:
    - Normal text input: 'hello world'
    - Special modifiers: '^' for Ctrl, '+' for Shift, '%' for Alt (e.g. '^a' for Ctrl+A, '^c' for Ctrl+C)
    - Special keys: {DELETE}, {ENTER}, {ESC}, {TAB}
    - Repeated keys: {TAB 2} to press TAB twice
    - Combined usage: '^+{ESC}' for Ctrl+Shift+Esc}
  • wheel_mouse_input args: {wheel_dist: integer for scroll distance (positive for scrolling up, negative for scrolling down)}
- rect: The bounding box coordinates [x1, y1, x2, y2] that define the target region where the action should be performed""",
                                "role": "system"
                            },
                            {
                                "content": f"""<image>
Please generate the next move according to the ui screenshot, instruction and previous actions.
Instruction: {task_instruction}
Previous actions: {history_actions}""",
                                "role": "user"
                            },
                            {
                                "content": f"""Observation: {obs_content}
Thought: {thought}
Low-level Instruction: {extract_action(act[k]["control_text"], act[k]["function"], act[k]["args"])}
Action: {action}""",
                                "role": "assistant"
                            }
                            ],
                            "images": [
                            obs[k]
                            ]
                        }
                        messages.append(m)
                        history_actions.append(extract_action(act[k]["control_text"], act[k]["function"], act[k]["args"]))
    return messages

# Load subtasks
with open(r"D:\data\succ_subtask_trajs.json", 'r', encoding='utf-8') as f:
    subtasks = json.load(f)
dic = {}
for i in subtasks:
    dic[i["subtask_id"]] = i

dag_dir = r"D:\data\[explicit_app]DAG_with_traj_topo_batch1"
json_files = [f for f in os.listdir(dag_dir) if f.endswith('.json') and f[:-5].isdigit()]

# Split files into 10 chunks
chunk_size = math.ceil(len(json_files) / 10)
file_chunks = [json_files[i:i + chunk_size] for i in range(0, len(json_files), chunk_size)]

# Process each chunk sequentially, but files within chunk in parallel
for chunk_idx, file_chunk in enumerate(file_chunks, 1):
    chunk_messages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_file = {
            executor.submit(process_file, os.path.join(dag_dir, filename), dic): filename 
            for filename in file_chunk
        }
        
        for future in tqdm(concurrent.futures.as_completed(future_to_file), 
                          total=len(file_chunk),
                          desc=f"Processing chunk {chunk_idx}/10"):
            chunk_messages.extend(future.result())
    
    # Save chunk results
    output_path = fr"D:\data\tuning_trajs_{chunk_idx}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunk_messages, f, ensure_ascii=False, indent=4)
