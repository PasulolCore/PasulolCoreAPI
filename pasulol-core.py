from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel, EmailStr
from bson.objectid import ObjectId
from decouple import config
from fastapi.routing import APIRouter
# Load environment variables
MONGO_URI = config("MONGO_URI", default="mongodb://localhost:27017/")
MONGO_DB_NAME = config("MONGO_DB_NAME", default="PasulolCoreAPI")
MONGO_DB_COLLECTION = config("MONGO_DB_COLLECTION", default="results")

class Result(BaseModel):
    _id: ObjectId
    email: EmailStr
    email_verification_token: str
    extroversion: int
    introversion: int
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

class Statistics(BaseModel):
    cumulative_visitors: int
    cumulative_shares: int

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": False})

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
results_collection = db[MONGO_DB_COLLECTION]

@app.get("/")
def read_root():
    return {"message": "Welcome to the MBTI API!"}

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

@result_router.get("/all", tags=["Results"])
def get_all_results():
    results = list(results_collection.find({}, {"_id": 0}))  # Exclude MongoDB's _id field
    return results

@result_router.get("/{result_id}", tags=["Results"])
def get_result_by_id(result_id: str):
    try:
        result = results_collection.find_one({"_id": ObjectId(result_id)})
        if result:
            result["_id"] = str(result["_id"])  # Convert ObjectId to string for JSON serialization
            return result
        raise HTTPException(status_code=404, detail="Result not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@result_router.post("/", tags=["Results"])
def create_result(result: Result):
    # Check if the Email already exists
    existing_result = results_collection.find_one({"email": result.email})
    if existing_result:
        raise HTTPException(status_code=400, detail="Email already exists")

    result_dict = result.dict()  # Convert Pydantic model to dictionary
    inserted_result = results_collection.insert_one(result_dict)
    return {"id": str(inserted_result.inserted_id), "message": "Result created successfully"}

@result_router.delete("/{result_id}", tags=["Results"])
def delete_result(result_id: str):
    try:
        delete_result = results_collection.delete_one({"_id": ObjectId(result_id)})
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Result not found")
        return {"message": "Result deleted successfully"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@result_router.put("/{result_id}", tags=["Results"])
def update_result(result_id: str, updated_result: Result):
    try:
        update_data = updated_result.dict()
        update_result = results_collection.update_one(
            {"_id": ObjectId(result_id)},
            {"$set": update_data}
        )
        if update_result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Result not found")
        return {"message": "Result updated successfully"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# Include the router in the main app
app.include_router(result_router, prefix="/result")

if __name__ == "__main__":
    import uvicorn
    from fastapi.routing import APIRouter
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")