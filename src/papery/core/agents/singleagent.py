# from papery.core.agents import Agent
# from typing import Any
# from papery.core.tools import call_tool


# class FullAgent(Agent):
#     """
#     An experimental singular agent for carrying out all tasks associated with this application.
#     """

#     def run(self, prompt: str) -> dict[str, Any]:
#         # Append our prompt to the message stack
#         self.context.append({"user": prompt})

#         # status_flags = ["done", "pending"]

#         latest_status_flag = "pending"
#         iteration = 0
#         while latest_status_flag == "pending" and iteration < self.max_iter:
#             self._call()

#     def _call(self):
#         response = self.model.call(self.context)

#         # Check status
#         if response.status == "done":
#             return response.contents
#         elif response.status == "pending":
#             if response.type == "call":
#                 self._process_tool_call(response.contents)
#             else:
#                 raise NotImplementedError(
#                     f"The returned type did not match schema: {response.type}"
#                 )
#         else:
#             raise NotImplementedError(
#                 f"The returned status did not match schema: {response.status}"
#             )

#     def _process_tool_call(self, tool):
#         tool_result = call_tool(tool)
#         self.context.append(tool_result)
