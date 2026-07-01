from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "success", "message": "Backend is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
