# CLIP Comparador V2 - Workspace Instructions

## Coding Guidelines
**IMPORTANT**: Only make changes that are explicitly requested. Do not add improvements, optimizations, or additional features unless specifically asked.

- **Fix only what's broken**: Address only the specific error or issue mentioned
- **Offer, don't implement**: Suggest improvements but only implement what's requested
- **Ask before adding**: If you think something needs improvement, ask first
- **Minimal changes**: Make the smallest change necessary to solve the problem

## Project Overview
CLIP Comparador V2 is a SaaS visual search system with dual architecture:

### Module 1: Backend Admin (Flask)
- **Location**: `clip_admin_backend/`
- **Port**: 5000
- **Function**: Client management, catalog administration, API key generation
- **Stack**: Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary

### Module 2: Search API (FastAPI)
- **Location**: `clip_search_api/`
- **Port**: 8000
- **Function**: Visual search endpoint with CLIP integration
- **Stack**: FastAPI + CLIP (ViT-B/16) + PostgreSQL (readonly) + Redis cache

## Project Structure
```
clip_comparador_v2/                  # V2 System Root
├── clip_admin_backend/              # Flask Admin Module
│   ├── app/
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── blueprints/             # Route handlers
│   │   ├── templates/              # Jinja2 templates
│   │   └── static/                 # CSS, JS, assets
│   └── app.py                      # Flask application
├── clip_search_api/                # FastAPI Search Module
│   ├── app/
│   │   ├── core/                  # CLIP Engine + Search Engine
│   │   ├── middleware/            # Auth + Rate Limiting
│   │   ├── models/                # Pydantic models
│   │   └── utils/                 # Database utilities
│   └── main.py                    # FastAPI application
├── shared/                         # Common resources
│   ├── database/                  # DB initialization scripts
│   └── docker/                    # Dockerfiles
├── docs/                          # Documentation
├── requirements.txt               # Python dependencies
├── .env.example                  # Environment template
├── .github/copilot-instructions.md  # This file
└── README.md                     # Project documentation
```

## Technology Stack
- **Backend Admin**: Flask 3.x + PostgreSQL + Redis + Bootstrap 5
- **Search API**: FastAPI + CLIP (ViT-B/16) + PostgreSQL (readonly) + Redis cache
- **Storage**: Cloudinary for images
- **Deployment**: Railway Hobby Plan ($5/month)
- **Database**: PostgreSQL with pgvector extension
- **Cache**: Redis for sessions and embeddings

## Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python shared/database/init_db.py

# Run Backend Admin
cd clip_admin_backend && python app.py

# Run Search API (separate terminal)
cd clip_search_api && python main.py
```

## Development Guidelines
- Use absolute imports consistently
- Follow Python PEP 8 standards
- Implement proper error handling and logging
- Use type hints for all function parameters
- Write comprehensive docstrings
- Separate concerns between admin and API modules
- Test both modules independently

## Railway Deployment
- Two independent services sharing PostgreSQL + Redis
- Optimized for Railway Hobby Plan constraints
- CPU-only CLIP processing (no GPU required)
- Environment-based configuration
- Automatic scaling and health checks

## Multi-Tenant Architecture
- Complete client isolation with UUID-based IDs
- Per-client API keys with individual rate limiting
- Shared database with client_id foreign keys
- Independent analytics and usage tracking

## Progress Tracking
- [x] Project structure created
- [x] Requirements.txt with all dependencies
- [x] Environment configuration template
- [x] Flask backend admin application foundation
- [x] Client and APIKey models implemented
- [x] FastAPI search API structure
- [x] CLIP engine and search engine cores
- [x] Authentication and rate limiting middleware
- [x] Database initialization scripts
- [x] Railway deployment configuration
- [x] Docker containers for both services
- [x] Comprehensive documentation
- [ ] Complete database models (Category, Product, etc.)
- [ ] Admin panel blueprints implementation
- [ ] Frontend templates and static assets
- [ ] API endpoint testing and validation
- [ ] Production deployment and testing

## Key Features Implemented
✅ **Multi-tenant SaaS architecture**
✅ **Dual service design (Admin + API)**
✅ **Railway Hobby Plan optimization**
✅ **CLIP-based visual search**
✅ **API key authentication system**
✅ **Rate limiting and security**
✅ **Cloudinary image storage**
✅ **PostgreSQL with pgvector**
✅ **Redis caching layer**
✅ **Docker containerization**

## Next Development Steps
1. Complete remaining database models
2. Implement admin panel blueprints
3. Create frontend templates with Bootstrap 5
4. Test Search API endpoints thoroughly
5. Deploy to Railway and validate functionality
6. Set up monitoring and analytics

## Reference V1 System
The original V1 system is available in the parent workspace (`../CLIP_Comparador/`) for format reference and comparison.

## API Documentation
- Backend Admin: http://localhost:5000
- Search API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- API Schema: http://localhost:8000/redoc
