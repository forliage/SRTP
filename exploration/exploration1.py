import os
import json
import uuid
import argparse
import time as t
from datetime import datetime
import random

from config.config import Config
from agents.agent import Agent
from envs.desktop_env import DesktopEnv

configs = Config.get_instance().config_data

path = configs["LOG_ROOT"]

related_apps = ["Cursor","ShareX","Zotero","Evernote","Windows PowerShell ISE"]

for i in range(1000):
    related_app = random.choice(related_apps)
    # related_app = "Windows PowerShell ISE"
    try:
        print(f"trajectory {i+1} / {100} is running...")
        id = str(uuid.uuid4())
        if not os.path.exists(f"{configs['LOG_ROOT']}/{id}"):
            os.makedirs(f"{configs['LOG_ROOT']}/{id}")
        env = DesktopEnv(
            path_to_vm=r"D:/Virtual_Machines/Windows 11 x64_1/Windows 11 x64.vmx", 
            observation_space=["Screen_A11Y"], # ["Screen", "A11Y", "Screen_A11Y", "SoM"]
            action_space="pyautogui", 
            snapshot_name="init_state", 
            headless=True,
            uuid=id,
            related_app=related_app,
        )
        # 等待虚拟机加载完成
        # t.sleep(20)
        agent = Agent(
            observation_space=["Screen_A11Y"],
            action_space="pyautogui",
            uuid=id,
            related_app=related_app,
        )
        # 每次探索前更新一下已有的subtask
        # 探索时提供resource的详细介绍，非必要不要新增resource
        step = 0
        while True:
            # 把第step步的obs存储在本地
            observation = env.get_observation()
            action, status = agent.get_action(observation)
            env.execute_action(action)
            
            step += 1
            agent.step = step
            env.step = step

            if status == "FINISH" or step > configs["MAX_STEP"]:
                break
    except Exception as e:
        print(e)
