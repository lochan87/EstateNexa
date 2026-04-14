import os
from groq import Groq
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings

persist_dir = "market_analysis/chroma_db"
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_vector_store():
    embeddings = HuggingFaceEmbeddings()

    # If DB exists → load
    if os.path.exists(persist_dir):
        return Chroma(persist_directory=persist_dir, embedding_function=embeddings)

    # Else → create
    docs = []
    folder = "market_analysis/Documents"

    for file in os.listdir(folder):
        if file.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(folder, file))
            docs.extend(loader.load())

    vectordb = Chroma.from_documents(
        docs,
        embedding=embeddings,
        persist_directory=persist_dir
    )
    vectordb.persist()

    return vectordb


def generate_market_analysis(query):
    try:
        vectordb = get_vector_store()
        retriever = vectordb.as_retriever()

        docs = retriever.invoke(query)

        if not docs:
            return "No market data found."

        content = "\n\n".join([doc.page_content for doc in docs])

        prompt = f"""
        Based on this market data:

        {content}

        Give:
        - Area summary
        - Price trends
        - Growth %
        - Investment recommendation
        """

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    except Exception as e:
        return str(e)