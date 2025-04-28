# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


from logging import Logger
from typing import Optional, Type

from agent.agent import FollowerAgent, HostAgent
from config.config import Config
from module.basic import BaseRound
from module.processors import follower_processor, processor

configs = Config.get_instance().config_data


class Round(BaseRound):
    """
    A round of a session in 
    """

    def __init__(
        self,
        task: str,
        host_agent: HostAgent,
        request: str,
        application: str,
        required_resources: str
    ) -> None:
        """
        Initialize a round.
        :param task: The name of current task.
        :param logger: The logger for the response and error.
        :param request_logger: The logger for the request string.
        :param host_agent: The host agent.
        :param request: The user request at the current round.
        """

        super().__init__(task, host_agent, request, application, required_resources)

    def process_application_selection(self) -> None:
        """
        Select an application to interact with.
        """

        host_agent_processor = self._create_host_agent_processor(
            processor.HostAgentProcessor
        )

        self._run_step(host_agent_processor)

        self.app_agent = self.host_agent.get_active_appagent()
        self.app_window = host_agent_processor.get_active_window()
        self.application = host_agent_processor.get_active_control_text()

    def process_action_selection(self) -> None:
        """
        Select an action with the application.
        """

        app_agent_processor = self._create_app_agent_processor(
            processor.AppAgentProcessor
        )
        self._run_step(app_agent_processor)


    def _create_host_agent_processor(
        self, processor_class: Type["processor.BaseProcessor"]
    ) -> processor.HostAgentProcessor:

        return processor_class(
            round_num=self.round_num,
            log_path=self.log_path,
            request=self.request,
            application=self.application,
            round_step=self.get_step(),
            session_step=self.session_step,
            host_agent=self.host_agent,
            prev_status=self.get_status(),
            app_window=self.app_window,
            required_resources=self.required_resources
        )

    def _create_app_agent_processor(
        self, processor_class: Type["processor.BaseProcessor"]
    ) -> processor.AppAgentProcessor:

        return processor_class(
            round_num=self.round_num,
            log_path=self.log_path,
            request=self.request,
            application=self.application,
            round_step=self.get_step(),
            session_step=self.session_step,
            process_name=self.application,
            app_agent=self.app_agent,
            app_window=self.app_window,
            control_reannotate=self.control_reannotate,
            prev_status=self.get_status(),
            required_resources=self.required_resources
        )


class FollowerRound(Round):

    def __init__(
        self,
        task: str,
        logger: Logger,
        request_logger: Logger,
        host_agent: HostAgent,
        app_agent: Optional[FollowerAgent],
        app_window: str,
        application: Optional[str],
        request: str,
    ) -> None:
        """
        Initialize a follower round.
        :param task: The name of current task.
        :param logger: The logger for the response and error.
        :param request_logger: The logger for the request string.
        :param host_agent: The host agent.
        :param app_agent: The app agent.
        :param app_window: The window of the application.
        :param application: The name of the application.
        :param request: The user request at the current round.
        """

        super().__init__(task, logger, request_logger, host_agent, request)

        self.app_agent = app_agent
        self.app_window = app_window
        self.application = application

    def process_application_selection(self) -> None:
        """
        Select an application to interact with.
        """

        host_agent_processor = self._create_host_agent_processor(
            follower_processor.FollowerHostAgentProcessor
        )

        self._run_step(host_agent_processor)

        self.app_agent = self.host_agent.get_active_appagent()
        self.app_window = host_agent_processor.get_active_window()
        self.application = host_agent_processor.get_active_control_text()

    def process_action_selection(self) -> None:
        """
        Select an action with the application.
        """

        app_agent_processor = follower_processor.FollowerAppAgentProcessor(
            round_num=self.round_num,
            log_path=self.log_path,
            request=self.request,
            round_step=self.get_step(),
            session_step=self.session_step,
            process_name=self.application,
            request_logger=self.request_logger,
            logger=self.logger,
            app_agent=self.app_agent,
            app_window=self.app_window,
            control_reannotate=self.control_reannotate,
            prev_status=self.get_status(),
        )

        app_agent_processor = self._create_app_agent_processor(
            follower_processor.FollowerAppAgentProcessor
        )
        self._run_step(app_agent_processor)


    def _create_app_agent_processor(
        self, processor_class: Type["processor.BaseProcessor"]
    ) -> follower_processor.AppAgentProcessor:
        """
        Create an app agent processor for the follower round.
        :param processor_class: The class of the processor.
        :return: The app agent processor.
        """

        return processor_class(
            round_num=self.round_num,
            log_path=self.log_path,
            request=self.request,
            round_step=self.get_step(),
            session_step=self.session_step,
            process_name=self.application,
            request_logger=self.request_logger,
            logger=self.logger,
            app_agent=self.app_agent,
            app_window=self.app_window,
            control_reannotate=self.control_reannotate,
            prev_status=self.get_status(),
        )
