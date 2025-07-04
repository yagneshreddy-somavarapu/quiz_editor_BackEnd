from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import pymongo

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
mycli = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = mycli["codingEditor"]
mycol_email = mydb["Emails"]
mycol_que = mydb["quesions"]

# Global email
email = ""

# Models
class EmailPassword(BaseModel):
    email: str
    password: str

class QueNos(BaseModel):
    queNo: str

class CodeData(BaseModel):
    code: str
    input: str = ""
    language_id: int

class TestData(BaseModel):
    code: str
    language_id: int
    queNo: str

# Judge0 local setup (on port 2360)
JUDGE0_URL = "http://localhost:2358/submissions"
HEADERS = {
    "Content-Type": "application/json"
}

# Routes
@app.post("/app/email")
async def email_login(data: EmailPassword):
    global email
    email = data.email
    password = data.password
    check = mycol_email.find_one({"email": email, "password": password})
    if check:
        return "sucss"
    else:
        return "User Email/Password incorrect"

@app.post("/app/quesions")
async def quesions(data: QueNos):
    que = mycol_que.find_one({"quesionNo": data.queNo})
    if que:
        return {
            "title": que.get("title"),
            "quesion": que.get("discription")
        }
    else:
        return {"error": "Question not found"}

@app.get("/app/user")
async def user():
    NoOfQue = list(mycol_que.find({}, {"_id": 0}))
    if NoOfQue:
        return {"email": email, "TotalQue": NoOfQue}
    else:
        return {"error": "No questions found"}

@app.post("/app/get_data")
async def get_data(data: CodeData):
    payload = {
        "language_id": data.language_id,
        "source_code": data.code,
        "stdin": data.input,
        "base64_encoded": False,
        "wait": True
    }
    try:
        response = requests.post(JUDGE0_URL, json=payload, headers=HEADERS)

        if response.status_code != 200:
            return {
                "error": f"Judge0 Error: {response.status_code}",
                "details": response.text
            }

        try:
            result = response.json()
            print("Judge0 response JSON:", result)

        except Exception:
            return {
                "error": "Invalid JSON received from Judge0",
                "details": response.text
            }

        output = ""
        if result.get("compile_output"):
            output = result["compile_output"]
        elif result.get("stderr"):
            output = result["stderr"]
        elif result.get("stdout"):
            output = result["stdout"]
        else:
            output = result.get("status", {}).get("description", "No output")
        print("Judge0 response JSON:", result)

        return {"output": output}

    except Exception as e:
        return {"error": "Request to Judge0 failed", "details": str(e)}

@app.post("/app/subinput")
async def subinput(data: TestData):
    question = mycol_que.find_one({"quesionNo": data.queNo})
    results = []
    count = 0

    if not question or "inputs" not in question:
        return {"error": "Invalid question or missing test cases"}

    for case in question["inputs"]:
        count += 1
        payload = {
            "language_id": data.language_id,
            "source_code": data.code,
            "stdin": case["input"],
            "base64_encoded": False,
            "wait": True
        }

        try:
            response = requests.post(JUDGE0_URL, json=payload, headers=HEADERS)

            if response.status_code != 200:
                results.append({
                    "input": case["input"],
                    "error": f"Judge0 returned {response.status_code}",
                    "details": response.text,
                    "test": count
                })
                continue

            try:
                result = response.json()
            except Exception:
                results.append({
                    "input": case["input"],
                    "error": "Invalid JSON from Judge0",
                    "details": response.text,
                    "test": count
                })
                continue

            output = ""
            if result.get("compile_output"):
                output = result["compile_output"]
            elif result.get("stderr"):
                output = result["stderr"]
            elif result.get("stdout"):
                output = result["stdout"]
            else:
                output = result.get("status", {}).get("description", "No output")

            passed = output.strip() == case["output"].strip()

            results.append({
                "input": case["input"],
                "stdout": output,
                "expetedout": case["output"],
                "passed": passed,
                "test": count
            })

        except Exception as e:
            results.append({
                "input": case["input"],
                "error": "Request failed",
                "details": str(e),
                "test": count
            })

    return results

