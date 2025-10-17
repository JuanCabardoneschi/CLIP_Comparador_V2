# CLIP Comparador V2 - Workspace Instructions

## Coding Guidelines
**IMPORTANT**: Only make changes that are explicitly requested. Do not add improvements, optimizations, or additional features unless specifically asked.

- **Fix only what's broken**: Address only the specific error or issue mentioned
- **Offer, don't implement**: Suggest improvements but only implement what's requested
- **Ask before adding**: If you think something needs improvement, ask first
- **Minimal changes**: Make the smallest change necessary to solve the problem

## Project Overview
CLIP Comparador V2 is a SaaS visual search system with unified Flask architecture:

### Unified Backend + Search API (Flask)
- **Location**: `clip_admin_backend/`
- **Port**: 5000
- **Functions**:
  - Admin panel: Client management, catalog administration, dynamic product attributes
  - Search API: `/api/search` endpoint with CLIP integration for visual similarity
- **Stack**: Flask 3.x + PostgreSQL + Redis + Bootstrap 5 + Cloudinary + CLIP (ViT-B/16)

## Project Structure
```
clip_comparador_v2/                  # V2 System Root
├── clip_admin_backend/              # Unified Flask Application
│   ├── app/
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── blueprints/             # Route handlers
│   │   │   ├── api.py             # Search API endpoint (/api/search)
│   │   │   ├── products.py        # Product CRUD with dynamic attributes
│   │   │   └── ...                # Other admin modules
│   │   ├── templates/              # Jinja2 templates
│   │   ├── static/                 # CSS, JS, assets, widget
│   │   ├── services/               # Cloudinary, Image Manager
│   │   └── utils/                  # Helpers and utilities
│   ├── migrations/                 # Alembic migrations
│   └── app.py                      # Flask application
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
- **Backend**: Flask 3.x + PostgreSQL + Redis + Bootstrap 5
- **ML/AI**: CLIP (ViT-B/16) for visual similarity search
- **Storage**: Cloudinary for images
- **Deployment**: Railway Hobby Plan ($5/month)
- **Database**: PostgreSQL with pgvector extension (REQUIRED - no SQLite support)
- **Cache**: Redis for sessions and embeddings
- **Dynamic Attributes**: JSONB-based flexible product metadata system

## Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Setup PostgreSQL local (REQUIRED)
# 1. Install PostgreSQL: https://www.postgresql.org/download/
# 2. Run setup script:
.\setup_postgres.ps1

# Setup environment
cp .env.local.example .env.local
# Edit .env.local with your PostgreSQL credentials

# Initialize database
python setup_local_postgres.py

# Run Flask Application (Admin + API)
cd clip_admin_backend && python app.py
# Acceso: http://localhost:5000
```

**Note**: PostgreSQL is REQUIRED. SQLite is not supported. See `docs/SETUP_POSTGRES_LOCAL.md` for detailed setup instructions.

## Development Guidelines
- Use absolute imports consistently
- Follow Python PEP 8 standards
- Implement proper error handling and logging
- Use type hints for all function parameters
- Write comprehensive docstrings
- Separate concerns between admin and API modules
- Test both modules independently

## Railway Deployment
- Single unified Flask service with PostgreSQL + Redis
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
- [x] Search API integrated in Flask (api.py blueprint)
- [x] CLIP engine for visual similarity
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
✅ **Unified Flask service (Admin + Search API)**
✅ **Railway Hobby Plan optimization**
✅ **CLIP-based visual search**
✅ **API key authentication system**
✅ **Rate limiting and security**
✅ **Cloudinary image storage**
✅ **PostgreSQL with pgvector**
✅ **Redis caching layer**
✅ **Dynamic product attributes (JSONB)**
✅ **Multi-select support for list attributes**

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
- Search API Endpoint: http://localhost:5000/api/search (POST)
- Widget Test: test-widget-railway.html
