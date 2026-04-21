import uvicorn

def main():
    uvicorn.run(
        "research_copilot.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )