# """
# A Flask API to allow the user to interact with AI Agents.
# """

# from flask import Flask, request
# from papery.controller import single_agent_controller

# app = Flask(__name__)

# @app.route("/call_single_agent", methods=["POST"])
# def call_single_agent():
#     data = request.get_json()
#     _validate_agent_call(data)

#     response = single_agent_controller(
#         prompt=data.get("prompt")
#     )
#     return response


# def _validate_agent_call(data):
