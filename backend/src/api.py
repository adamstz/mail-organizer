from fastapi import FastAPI

app = FastAPI(title="organize-mail backend")


@app.get("/health")
async def health():
    return {"status": "ok"}

