from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings  # or your used embedding class
import pickle

with open("faiss_annual/index.pkl", "rb") as f:
    vectorstore = pickle.load(f)

# Sample check
docs = vectorstore.similarity_search("m&m", k=3)
for doc in docs:
    print(doc.metadata)
