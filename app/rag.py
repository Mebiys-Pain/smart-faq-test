import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Qdrant
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import ChatPromptTemplate
from qdrant_client import QdrantClient
from app.config import settings

# 1. Настройка моделей
print("Loading local embedding model...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.3
)

# 2. Функция загрузки документов (Оставляем как было, она работает)
async def ingest_docs(folder_path: str = "documents"):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return {"status": "empty", "message": "Folder created, please add PDFs"}

    loader = DirectoryLoader(folder_path, glob="*.pdf", loader_cls=PyPDFLoader)
    docs = loader.load()
    
    if not docs:
        return {"status": "empty", "message": "No PDF files found"}

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    try:
        # Тут используем LangChain для удобной загрузки - это работает
        Qdrant.from_documents(
            splits,
            embeddings,
            url=settings.QDRANT_URL,
            collection_name="faq_collection",
            force_recreate=True 
        )
        return {"status": "success", "chunks": len(splits), "message": "Embeddings created locally!"}
    except Exception as e:
        return {"status": "error", "details": str(e)}

# 3. Функция поиска ответа (ПЕРЕПИСАНА НА ПРЯМОЙ ЗАПРОС)
async def ask_llm(question: str):
    try:
        # 1. Превращаем вопрос в вектор вручную
        query_vector = embeddings.embed_query(question)
        
        # 2. Ищем в базе напрямую через клиент (минуя баги LangChain)
        client = QdrantClient(url=settings.QDRANT_URL)
        hits = client.search(
            collection_name="faq_collection",
            query_vector=query_vector,
            limit=3
        )
        
        # 3. Если ничего не нашли
        if not hits:
            return "Я не нашел информации в документах. Попробуйте загрузить базу знаний.", []

        # 4. Вытаскиваем текст из результатов
        # Qdrant хранит текст внутри payload -> page_content
        context_text = ""
        source_names = set()
        
        for hit in hits:
            # Безопасно достаем текст
            text = hit.payload.get("page_content", "")
            context_text += text + "\n\n"
            
            # Достаем источник (имя файла)
            meta = hit.payload.get("metadata", {})
            if "source" in meta:
                source_names.add(meta["source"])

        # 5. Отправляем в Gemini
        template = """Ты — умный помощник службы поддержки. 
        Используй ТОЛЬКО следующий контекст, чтобы ответить на вопрос. 
        Если ответа нет в контексте, скажи "Я не знаю ответа на основе предоставленных документов".
        
        Контекст:
        {context}
        
        Вопрос: {question}
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm
        
        response = await chain.ainvoke({"context": context_text, "question": question})
        return response.content, list(source_names)

    except Exception as e:
        print(f"Error details: {e}")
        return f"Ошибка при генерации: {str(e)}", []