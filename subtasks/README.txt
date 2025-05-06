metadata.json
其中包含了324个子任务的meatadata，每个子任务包括以下9个属性：
- id：uuid，用来唯一标识子任务
- instruction_template：子任务指令模板，其中包含参数占位符
- application：该子任务属于的应用程序名
- available_parameters：所有可以设置的参数列表，可用于实例化多样的instruction，其中每个列表元素代表一组参数
- OS：该子任务所属的操作系统
- required_resources：该子任务所需的前置资源列表
- produced_resources：该子任务所产生的后续资源列表
- function：子任务的函数表现形式
- function_name：子任务对应的函数名

trajectory.json
其中包含了255个经过校验过的子任务执行轨迹，每条执行轨迹包括以下5个属性：
- trajectory_id：轨迹的唯一标识符
- instruction：实例化后的指令，使用subtask中第一组available_parameters来实例化
- observations：轨迹对应的每一步截图列表
- actions：轨迹对应的每一步操作列表
- subtask_id：该轨迹对应的子任务id

eval_functions
其中包含了301个子任务评估函数，需要搭配虚拟机一起使用
