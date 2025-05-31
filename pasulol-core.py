from fastapi import FastAPI, HTTPException, BackgroundTasks
from pymongo import MongoClient
from pydantic import BaseModel, EmailStr, Field
from pydantic.json_schema import SkipJsonSchema
from bson.objectid import ObjectId
from decouple import config
from fastapi.routing import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from cryptography.fernet import Fernet
import smtplib

# Load environment variables
MONGO_URI = config("MONGO_URI", default="mongodb://localhost:27017/")
MONGO_DB_NAME = config("MONGO_DB_NAME", default="PasulolCoreAPI")
MONGO_DB_COLLECTION = config("MONGO_DB_COLLECTION", default="results")
UI_URL = config("UI_URL", default="https://localhost:4200")
API_URL = config("API_URL", default="https://localhost:8000")
# Replace with your SMTP server details
SMTP_SERVER = config("SMTP_SERVER", default="smtp.example.com")
SMTP_PORT = config("SMTP_PORT", default=587)
SMTP_USER = config("SMTP_USER", default="example@gmail.com")
SMTP_PASSWORD = config("SMTP_PASSWORD", default="your-email-password")

class Result(BaseModel):
    _id: ObjectId
    accept_email: bool
    email: SkipJsonSchema[EmailStr] = Field(exclude=True, default=None)
    email_verification_token: SkipJsonSchema[str] = Field(exclude=True, default=None)
    extroversion: int
    introversion: int
    sensing: int
    intuition: int
    thinking: int
    feeling: int
    judging: int
    perceiving: int
    enneagram_1: int
    enneagram_2: int
    enneagram_3: int
    enneagram_4: int
    enneagram_5: int
    enneagram_6: int
    enneagram_7: int
    enneagram_8: int
    enneagram_9: int
    headType: int
    heartType: int
    gutType: int

class Statistics(BaseModel):
    cumulative_visitors: int
    cumulative_shares: int

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": False})

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],  # Allow requests from the UI URL and localhost # TODO: Don't forget to change this to your actual UI_URL in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

ENCRYPTION_KEY = config("ENCRYPTION_KEY", default=Fernet.generate_key().decode())

def encrypt_email_verification_token(email: str) -> str:
    try:
        fernet = Fernet(ENCRYPTION_KEY.encode())
        encrypted_token = fernet.encrypt(email.encode())
        return encrypted_token.decode()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")

# Email sending function
def send_verification_email(email: str, token: str, result_id: str):
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create a MIMEText message with UTF-8 encoding
            msg = MIMEMultipart()
            msg["Subject"] = "การยืนยันอีเมล"
            msg["From"] = f"PasulolCore <{SMTP_USER}>"
            msg["To"] = email
            body = f"กรุณากดไปที่ลิงก์นี้เพื่อยืนยันอีเมลของคุณให้ผูกไว้กับผลลัพธ์: {API_URL}/result/{result_id}/verify-email?email={email}&token={token}\n\nขอบคุณที่ใช้บริการ PasulolCore!"
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Send the email
            server.sendmail(SMTP_USER, email, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
results_collection = db[MONGO_DB_COLLECTION]

@app.get("/")
def read_root():
    return {"message": "Welcome to the PasulolCoreAPI!"}

result_router = APIRouter()

@result_router.get("/statistics", tags=["Statistics"])
def get_statistics():
    try:
        stats = db.statistics.find_one({}, {"_id": 0})  # Exclude MongoDB's _id field
        if stats:
            return stats
        raise HTTPException(status_code=404, detail="Statistics not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@result_router.post("/visit", tags=["Statistics"])
def record_visit():
    try:
        db.statistics.update_one(
            {},
            {"$inc": {"cumulative_visitors": 1}},
            upsert=True
        )
        return {"message": "Visit recorded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@result_router.post("/share", tags=["Statistics"])
def record_share():
    try:
        db.statistics.update_one(
            {},
            {"$inc": {"cumulative_shares": 1}},
            upsert=True
        )
        return {"message": "Share recorded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@result_router.get("/{result_id}", tags=["Results"])
def get_result_by_id(result_id: str):
    try:
        result = results_collection.find_one({"_id": ObjectId(result_id)}, {"email_verification_token": 0, "email": 0})  # Exclude email_verification_token and email fields
        if result:
            result["_id"] = str(result["_id"])  # Convert ObjectId to string for JSON serialization
            return result
        raise HTTPException(status_code=404, detail="Result not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@result_router.post("/{result_id}/send-verification", tags=["Email Verification"])
def send_email_verification(email: EmailStr, result_id: str, background_tasks: BackgroundTasks):
    result = results_collection.find_one({"_id": ObjectId(result_id)})
    if result.get("accept_email") is False:
        raise HTTPException(status_code=400, detail="This result no longer accepts email")
    # Generate the token
    token = encrypt_email_verification_token(email)

    # Update the email_verification_token in the database
    result = results_collection.find_one({ "_id": ObjectId(result_id) }, {"email_verification_token": 0})  # Exclude email_verification_token field
    if result:
        if not result.get("accept_email", True):
            raise HTTPException(status_code=400, detail="This result no longer accepts email")
        results_collection.update_one(
            {"_id": ObjectId(result_id)},
            {"$set": {"email_verification_token": token}}
        )
    else:
        raise HTTPException(status_code=404, detail=f"Result with id of {result_id} not found")

    # Send the verification email
    background_tasks.add_task(send_verification_email, email, token, result_id)
    return {"message": "Verification email sent successfully"}

@result_router.get("/{result_id}/verify-email", tags=["Email Verification"])
def verify_email(email: EmailStr, token: str, result_id: str):
    result = results_collection.find_one({"_id": ObjectId(result_id)})
    if result.get("accept_email") is False:
        raise HTTPException(status_code=400, detail="This result no longer accepts email")
    try:
        result = results_collection.find_one({"_id": ObjectId(result_id)}, {"email_verification_token": 1})
        if result.get("email_verification_token") != token:
            raise HTTPException(status_code=400, detail="Invalid token")
        results_collection.update_one(
            {"_id": ObjectId(result_id)},
            {"$set": {"email": email, "accept_email": False}},
            upsert=True
        )
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create a MIMEText message with UTF-8 encoding
            msg = MIMEMultipart()
            msg["Subject"] = "ผลลัพธ์ของการทำแบบทดสอบ"
            msg["From"] = f"PasulolCore <{SMTP_USER}>"
            msg["To"] = email
            body = f"การผูกอีเมลเข้ากับผลลัพธ์สำเร็จ\n\nดูผลลัพธ์ของคุณได้ที่: \n{UI_URL}/result/{result_id}\n\nขอบคุณที่ใช้บริการ PasulolCore!"
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Send the email
            server.sendmail(SMTP_USER, email, msg.as_string())
        return {"message": "Your email successfully linked into your result"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@result_router.post("/create", tags=["Results"])
def create_result(result: Result):
    # Exclude restricted fields from the request body
    result_dict = result.dict()
    inserted_result = results_collection.insert_one(result_dict)
    return {"id": str(inserted_result.inserted_id), "message": "Result created successfully"}

# Include the router in the main app
app.include_router(result_router, prefix="/result")

import threading
import requests
import time
def log_api_results():
    while True:
        try:
            response = requests.get("https://pasulolcoreapi.onrender.com/")
            if response.status_code == 200:
                print("API Response:", response.json())
            else:
                print(f"Failed to fetch API data. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error occurred while calling API: {e}")
        time.sleep(360) # 6 minutes

if __name__ == "__main__":
    # Start the API logging in a separate thread
    api_logging_thread = threading.Thread(target=log_api_results, daemon=True)
    api_logging_thread.start()

    import uvicorn
    # Run the FastAPI application
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")