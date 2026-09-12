import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "literature_ai.review_service.api:app", host="0.0.0.0", port=8002, reload=False
    )
