# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from typing import List

from module.basic import BaseSession
from module.processors import follower_processor, processor
from module.state import Status
from config.config import Config
configs = Config.get_instance().config_data

class Client:
    """
    A client to run the system for a single session.
    """

    def __init__(self, session: BaseSession) -> None:
        """
        Initialize a client.
        """

        self.session = session

    def run(self) -> None:
        """
        Run the client.
        """
        # Manually call HostAgent to create AppAgent, skipping the step of app selection.
        self.session._current_round = self.session.create_round()
        current_round = self.session.get_current_round()
        host_agent_processor = current_round._create_host_agent_processor(
            processor.HostAgentProcessor
        )
        host_agent_processor.create_sub_agent()
        current_round.app_agent = current_round.host_agent.get_active_appagent()
        self.session.app_agent = self.session.host_agent.get_active_appagent()

        # AppAgent selects operations until the task is completed.
        while self.session._status != Status.FINISH and self.session.get_step() <= configs["MAX_STEP"]:
            self.session.handle()

        # self.session.print_cost()

