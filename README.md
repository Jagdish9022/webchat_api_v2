# Web Scraping Q&A Chatbot 🤖

An intelligent chatbot that scrapes websites and answers questions using vector embeddings, Qdrant vector database, and Google's Gemini AI.

## 🚀 Features

- **Web Scraping**: Automatically crawls and extracts content from websites
- **Vector Search**: Uses sentence transformers for semantic search
- **AI-Powered Answers**: Leverages Google Gemini for intelligent responses
- **RESTful API**: Clean FastAPI endpoints for easy integration
- **Scalable Storage**: Qdrant vector database for efficient similarity search
- **Robust Error Handling**: Comprehensive logging and error management

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Scraper   │───▶│   Text Chunker  │───▶│   Embeddings    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gemini AI     │◀───│  Vector Search  │◀───│   Qdrant DB     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- Docker (for Qdrant)
- Google Gemini API Key

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd web-scraping-qa-chatbot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   ```

5. **Start Qdrant database**
   ```bash
   docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
   ```

6. **Run the application**
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
web-scraping-qa-chatbot/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables
├── .gitignore            # Git ignore rules
├── README.md             # Project documentation
└── app/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes.py      # API endpoint definitions
    ├── db/
    │   ├── __init__.py
    │   ├── models.py      # Pydantic models
    │   └── qdrant.py      # Qdrant database operations
    ├── services/
    │   ├── __init__.py
    │   ├── embeddings.py  # Text embedding generation
    │   └── gemini.py      # Gemini AI integration
    └── utils/
        ├── __init__.py
        ├── common.py      # Web scraping utilities
        └── logger.py      # Logging configuration
```

## 🌐 API Endpoints

### Health Check
```http
GET /health
```
Returns the health status of the application.

### List Collections
```http
GET /collections
```
Returns all available document collections.

### Scrape and Ingest
```http
POST /scrape-and-ingest
Content-Type: application/json

{
  "url": "https://example.com"
}
```
Scrapes the website and ingests content into the vector database.

### Ask Question
```http
POST /ask-question
Content-Type: application/json

{
  "question": "What is this website about?",
  "collection_name": "collection_hash_from_ingest"
}
```
Asks a question based on the ingested website content.

## 💡 Usage Examples

### 1. Using cURL

**Scrape a website:**
```bash
curl -X POST "http://localhost:8000/scrape-and-ingest" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://docs.python.org"}'
```

**Ask a question:**
```bash
curl -X POST "http://localhost:8000/ask-question" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Python?", "collection_name": "abc123def456"}'
```

### 2. Using Python requests

```python
import requests

# Scrape and ingest
response = requests.post(
    "http://localhost:8000/scrape-and-ingest",
    json={"url": "https://fastapi.tiangolo.com/"}
)
collection_name = response.json()["collection_name"]

# Ask question
response = requests.post(
    "http://localhost:8000/ask-question",
    json={
        "question": "How do I create a FastAPI application?",
        "collection_name": collection_name
    }
)
print(response.json()["answer"])
```

### 3. Using JavaScript/Fetch

```javascript
// Scrape and ingest
const scrapeResponse = await fetch('http://localhost:8000/scrape-and-ingest', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({url: 'https://example.com'})
});
const {collection_name} = await scrapeResponse.json();

// Ask question
const qaResponse = await fetch('http://localhost:8000/ask-question', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    question: 'What does this website offer?',
    collection_name: collection_name
  })
});
const {answer} = await qaResponse.json();
console.log(answer);
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `QDRANT_HOST` | Qdrant database host | `localhost` |
| `QDRANT_PORT` | Qdrant database port | `6333` |

### Customization Options

- **Chunk Size**: Modify `chunk_size` in `common.py` (default: 1000)
- **Overlap**: Adjust `chunk_overlap` in `common.py` (default: 200)
- **Max Pages**: Change `max_pages` in crawling function (default: 10)
- **Vector Dimensions**: Update `VECTOR_SIZE` in `qdrant.py` (default: 384)

## 🚨 Error Handling

The application includes comprehensive error handling:

- **Network Errors**: Retry mechanisms for web scraping
- **API Errors**: Graceful handling of Gemini API failures
- **Database Errors**: Qdrant connection and query error handling
- **Validation Errors**: Input validation with detailed error messages

## 📊 Monitoring and Logging

Logs are written to console with timestamps and log levels:
```
[2024-01-15 10:30:45] INFO - Application startup: Services initialized.
[2024-01-15 10:31:12] INFO - Crawling: https://example.com
[2024-01-15 10:31:15] INFO - Generated 25 text chunks
```

## 🔧 Troubleshooting

### Common Issues

1. **Qdrant Connection Error**
   ```
   Solution: Ensure Qdrant is running on the correct port (6333)
   ```

2. **Gemini API Error**
   ```
   Solution: Check your API key and quota limits
   ```

3. **Web Scraping Failures**
   ```
   Solution: Some websites block scrapers; try different user agents
   ```

### Debug Mode

Run with debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🚀 Deployment

### Docker Deployment

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   EXPOSE 8000
   CMD ["python", "main.py"]
   ```

2. **Docker Compose**
   ```yaml
   version: '3.8'
   services:
     app:
       build: .
       ports:
         - "8000:8000"
       environment:
         - GEMINI_API_KEY=${GEMINI_API_KEY}
         - QDRANT_HOST=qdrant
     qdrant:
       image: qdrant/qdrant
       ports:
         - "6333:6333"
   ```

### Production Considerations

- Use environment-specific configurations
- Implement rate limiting
- Add authentication for sensitive endpoints
- Use HTTPS in production
- Monitor resource usage and scaling

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Qdrant](https://qdrant.tech/) - Vector similarity search engine
- [Google Gemini](https://ai.google.dev/) - Large language model
- [Sentence Transformers](https://www.sbert.net/) - Text embeddings
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing

## 📞 Support

For support and questions:
- Create an issue in the repository
- Contact: [your-email@example.com]
- Documentation: [Link to detailed docs]

---

**Made with ❤️ by AI Team**