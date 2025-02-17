from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def index():
    return "Hello MLOps!"

@app.get("/data")
def inference_api():
    return {"result": "ok"}

