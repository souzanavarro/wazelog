import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Wazelog FastAPI backend online!"}
