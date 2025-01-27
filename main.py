from fastapi import FastAPI

app = FastAPI()

# http://localhost:8000

@app.get("/")
def index():
    return "Hello MLOps!"

