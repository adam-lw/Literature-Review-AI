import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "literature_ai.agent_service.api:app", host="0.0.0.0", port=8001, reload=False
    )
