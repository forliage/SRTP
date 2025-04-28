import logging
import os
import subprocess
import time
from typing import Callable, Any, Optional, Tuple
from typing import List, Dict, Union

import gymnasium as gym

def _execute_command(command: List[str]) -> None:
    def _is_contained_in(a, b):
        for v in set(a):
            if a.count(v) > b.count(v):
                return False
        return True

    # Specially handled for the `vmrun` command in Windows
    if _is_contained_in(["vmrun", "-T", "ws", "start"], command):
        p = subprocess.Popen(command)
        p.wait()
    else:
        result = subprocess.run(command, stdout=subprocess.PIPE, timeout=60, text=True, encoding="utf-8")
        
        return result.stdout


class DesktopEnv(gym.Env):
    """
    DesktopEnv with OpenAI Gym interface. It provides a desktop environment for setting and evaluating desktop automation tasks.
    """

    def __init__(
            self,
            path_to_vm: str,
            snapshot_name: str = "init_state",
            action_space: str = "computer_13",
            cache_dir: str = "cache",
            screen_size: Tuple[int] = (1920, 1080),
            headless: bool = False,
            require_a11y_tree: bool = True,
            require_terminal: bool = False,
    ):
        """
        Args:
            path_to_vm (str): path to .vmx file
            snapshot_name (str): snapshot name to revert to, default to "init_state"
            action_space (str): "computer_13" | "pyautogui"
            cache_dir (str): cache directory to cache task-related stuffs like
              reference file for evaluation
            screen_size (Tuple[int]): screen size of the VM
            headless (bool): whether to run the VM in headless mode
            require_a11y_tree (bool): whether to require accessibility tree
            require_terminal (bool): whether to require terminal output
        """

        # Initialize environment variables
        self.path_to_vm = os.path.abspath(os.path.expandvars(os.path.expanduser(path_to_vm)))
        self.snapshot_name = snapshot_name
        self.cache_dir_base: str = cache_dir
        self.vm_screen_size = screen_size  # todo: add the logic to get the screen size from the VM
        self.headless = headless
        self.require_a11y_tree = require_a11y_tree
        self.require_terminal = require_terminal

        _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "revertToSnapshot", self.path_to_vm, self.snapshot_name])
        time.sleep(5)
        self._start_emulator()
        self.vm_ip = self._get_vm_ip()
    def _start_emulator(self):
        while True:
            output = subprocess.check_output("vmrun -T ws list", shell=True, stderr=subprocess.STDOUT)
            output = output.decode()
            output: List[str] = output.splitlines()
            # if self.path_to_vm.lstrip("~/") in output:
            if self.path_to_vm in output:
                break
            else:
                _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "start", self.path_to_vm]) if not self.headless \
                    else _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "start", self.path_to_vm, "nogui"])
                time.sleep(3)

    def _get_vm_ip(self):
        max_retries = 20
        for _ in range(max_retries):
            try:
                output = _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "getGuestIPAddress", self.path_to_vm, "-wait"]).strip()
                return output
            except Exception as e:
                print(e)
                time.sleep(5)
        raise Exception("Failed to get VM IP address!")
