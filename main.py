from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from typing import List,Dict
import requests
import base64
import pymongo
import pandas as pd
from io import BytesIO
from fastapi.encoders import jsonable_encoder

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mycli = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = mycli["codingEditor"]
mycol_email = mydb["Emails"]
mycol_que = mydb["quesions"]

class EmailPassword(BaseModel):
    email: str
    password: int
@app.post("/app/email")
async def email(data: EmailPassword):
    global email 
    email = data.email 
    password = data.password
    check = mycol_email.find_one({"email":email,"password":password})
    if check:
       return "sucss"
    else:
        return "User Email/Password incorrect"
    


class QueNos(BaseModel):
    queNo : str

@app.post("/app/quesions")
async def quesions(data : QueNos):
    # print("quesion number >> 2")
    que = mycol_que.find_one({"quesionNo":data.queNo})
    first_input = que["inputs"][0]["input"] if que.get("inputs") else ""
    return {
        "title": que.get("title"),
        "quesion": que.get("discription"),
        "first_input": first_input
    }

@app.get("/app/user")
async def user():
    NoOfQue = list(mycol_que.find({},{"_id":0}))
    if NoOfQue:
    #    print("totalQue >>> ",NoOfQue["quesionNo"])
       return {"email":email , "TotalQue":NoOfQue}
    else:
        return "err"
# Judge0 API details
JUDGE0_URL = "https://judge0-ce.p.rapidapi.com/submissions"
HEADERS = {
    "X-RapidAPI-Key": "640db5e88bmsh0e7bf6495c90995p1cad09jsn5cec7c140fdf",
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
    "Content-Type": "application/json"
}



# Request schema
class CodeData(BaseModel):
    code: str
    input: str = ""
    language_id: int

@app.post("/app/get_data")
async def get_data(data: CodeData):
    # Encode for Judge0
    source_code = base64.b64encode(data.code.encode()).decode()
    stdin = base64.b64encode(data.input.encode()).decode()

    payload = {
        "language_id": data.language_id,
        "source_code": source_code,
        "stdin": stdin
    }

    # Send to Judge0
    response = requests.post(
        f"{JUDGE0_URL}?base64_encoded=true&wait=true",
        json=payload,
        headers=HEADERS
    )
    result = response.json()
    # Decode outputs
    output = ""
    if result.get("compile_output"):
        output = base64.b64decode(result["compile_output"]).decode()
    elif result.get("stderr"):
        output = base64.b64decode(result["stderr"]).decode()
    elif result.get("stdout"):
        output = base64.b64decode(result["stdout"]).decode()
    else:
        output = result.get("status", {}).get("description", "No output")
    return {"output":output}

class TestData(BaseModel):
      code: str
      language_id: int
      queNo:str
@app.post("/app/subinput")
def subinput(data : TestData):
    code = data.code
    question = mycol_que.find_one({"quesionNo": data.queNo})
    results = []
    count = 0
    for case in question["inputs"]:
        count += 1
        try:
            _ = list(map(int, case["input"].split()))
        except ValueError:
            return {"error": f"Invalid input format in test case {case['test']}: {case['input']}"}
        payload = {
           "language_id": data.language_id,
           "source_code": code,
           "stdin": case["input"]
        } 

# Send to Judge0
        response = requests.post(
            JUDGE0_URL + "?base64_encoded=false&wait=true",
            headers=HEADERS,
            json=payload
        )
        # resp_data = response.json()
        result = response.json()
    # Decode outputs
      
        output = result.get("stdout", "").strip() if result.get("stdout") else ""
        passed = output == case["output"]
        results.append({
          "input": case["input"],
          "stdout": output,
          "expetedout":case["output"],
          "passed": passed,
          "test":count
         })
    return results

@app.post("/app/admin")
async def admin(file: UploadFile = File(...)):
    # Read the uploaded Excel file
    contents = await file.read()
    excel_data = BytesIO(contents)
    # Convert bytes to pandas DataFrame
    df = pd.read_csv(excel_data)
    df["marks"] = 0
    df["Attempt"] = "Not Attempt"
    Excel_data = df.to_dict(orient='records')
    
    # print(dff)
    Mongo_data = mycol_email.find({},{"_id":0})
    if Mongo_data:
        Mongo_list = [rec["email"] for rec in Mongo_data]
        result = 0
        duplicates = 0
        for data in Excel_data:
            if data["email"] not in Mongo_list:
                mycol_email.insert_one(data)
                result += 1
            else:
                duplicates += 1
    else:
        duplicates = 0
        mycol_email.insert_many(Excel_data)
        result = len(Excel_data)
    total = len(list(mycol_email.find({},{"_id":0})))
    return {"AddData":result,"TotalData":total,"Duplicates":duplicates}

@app.get("/app/dele")
def dele():
    mycol_email.delete_many({})
    return "delete sucess"
@app.get('/app/datashow')
def datashow():
    data = mycol_email.find({},{"_id":0})
    result = []
    for item in data:
        result.append(item)
    return result