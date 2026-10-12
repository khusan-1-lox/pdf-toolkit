import os
import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PDF_TOOLKIT_PORT", "8000")), log_level="info")
