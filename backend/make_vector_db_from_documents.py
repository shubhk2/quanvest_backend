from pymongo import MongoClient
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm
import os

# Load .env file
load_dotenv()

# === MongoDB config ===
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "financial_documents")
COLLECTION_NAME = "earnings_calls_fy25"  # new collection name

# === Connect ===
client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLLECTION_NAME]

# === Embedding model ===
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# === Text splitter ===
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

# === Read and chunk documents ===
documents = []
cursor = collection.find({})
for doc in tqdm(cursor, desc="Preparing documents"):
    ticker = doc.get("ticker")
    year = doc.get("year")
    quarter = doc.get("quarter")
    source = doc.get("source", "earnings_call")
    text = doc.get("text", "")
    if not text.strip():
        continue

    chunks = splitter.split_text(text)
    for i, chunk in enumerate(chunks):
        documents.append(Document(
            page_content=chunk,
            metadata={
                "ticker": ticker,
                "year": year,
                "quarter": quarter,
                "source": source,
                "chunk_index": i
            }
        ))

# === Embed and build FAISS DB ===
print("Creating FAISS vector DB for earnings calls...")
db = FAISS.from_documents(documents, embedding=embedding_model)

# === Save to new folder ===
db.save_local("faiss_earnings_quarters")  # your new FAISS index directory

print("✅ Earnings Calls embedded and saved to faiss_earnings/")
