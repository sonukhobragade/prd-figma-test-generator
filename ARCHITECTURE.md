# Architecture Documentation

> **Version**: 2.0.0
> **Last Updated**: 2025-10-08
> **Status**: Proposed Clean Architecture Restructure

## 📋 Table of Contents
- [Overview](#overview)
- [Architectural Principles](#architectural-principles)
- [Project Structure](#project-structure)
- [Layer Responsibilities](#layer-responsibilities)
- [Module Organization](#module-organization)
- [Data Flow](#data-flow)
- [Environment Configuration](#environment-configuration)
- [Testing Strategy](#testing-strategy)
- [CI/CD Integration](#cicd-integration)
- [Scalability Patterns](#scalability-patterns)

---

## 🎯 Overview

This project follows **Clean Architecture** (also known as Hexagonal/Ports & Adapters Architecture) to ensure:

- **Framework Independence**: Business logic doesn't depend on FastAPI, React, or any external library
- **Testability**: Each layer can be tested in isolation
- **Scalability**: Easy to split into microservices or keep as monorepo
- **Maintainability**: Clear separation of concerns with single-responsibility modules

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌─────────────────┐              ┌─────────────────┐      │
│  │   Web UI (React) │              │  API (FastAPI)  │      │
│  └─────────────────┘              └─────────────────┘      │
└───────────────────────┬───────────────────┬─────────────────┘
                        │                   │
┌───────────────────────┴───────────────────┴─────────────────┐
│                    APPLICATION LAYER                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Use Cases / Application Services          │    │
│  │  - Analyze PRD     - Process Figma Design          │    │
│  │  - Generate Tests  - Expand Test Cases             │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│                     DOMAIN LAYER                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │           Business Logic / Entities                 │    │
│  │  - Test Models    - Analysis Rules                  │    │
│  │  - Validation     - Business Rules                  │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────┴────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Figma API   │  │ Anthropic AI │  │ File Storage │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Architectural Principles

### 1. **Dependency Rule**
- Dependencies point **inward only**
- Domain layer has **zero external dependencies**
- Infrastructure depends on domain, not vice versa

### 2. **Clean Architecture Layers**

| Layer | Purpose | Dependencies | Examples |
|-------|---------|--------------|----------|
| **Domain** | Business entities & rules | None | `TestCase`, `PRDDocument`, `ValidationRules` |
| **Application** | Use cases & orchestration | Domain | `AnalyzePRDUseCase`, `GenerateTestsUseCase` |
| **Infrastructure** | External integrations | Domain + Application | `FigmaAPIAdapter`, `AnthropicLLMAdapter` |
| **Presentation** | UI & API interfaces | Application | FastAPI routes, React components |

### 3. **Single Responsibility Principle**
Each module/class has **one reason to change**:
- `FigmaAPIAdapter` → Changes only when Figma API changes
- `AnalyzePRDUseCase` → Changes only when business requirements change
- `TestCaseEntity` → Changes only when domain rules change

### 4. **Open/Closed Principle**
- Open for extension, closed for modification
- Use interfaces/protocols for extensibility

### 5. **Liskov Substitution Principle**
- All adapters are interchangeable through interfaces
- Can swap `AnthropicLLM` with `OpenAILLM` without changing use cases

---

## 📁 Project Structure

### Proposed Clean Architecture Structure

```
prd-figma-test-generator/
│
├── 📂 packages/                    # Monorepo packages (future: microservices)
│   │
│   ├── 📦 backend/                 # Backend service
│   │   ├── src/
│   │   │   ├── domain/            # ❤️ Core business logic (framework-independent)
│   │   │   │   ├── entities/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── test_case.py
│   │   │   │   │   ├── prd_document.py
│   │   │   │   │   ├── figma_design.py
│   │   │   │   │   └── test_checklist.py
│   │   │   │   ├── value_objects/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── priority.py
│   │   │   │   │   ├── test_type.py
│   │   │   │   │   └── coverage_score.py
│   │   │   │   ├── repositories/  # Interfaces (not implementations)
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── prd_repository.py
│   │   │   │   │   ├── figma_repository.py
│   │   │   │   │   └── llm_repository.py
│   │   │   │   ├── services/      # Domain services
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── test_validator.py
│   │   │   │   │   └── coverage_calculator.py
│   │   │   │   └── exceptions/
│   │   │   │       ├── __init__.py
│   │   │   │       └── domain_exceptions.py
│   │   │   │
│   │   │   ├── application/       # 🎯 Use cases & application services
│   │   │   │   ├── use_cases/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── analyze_prd.py
│   │   │   │   │   ├── analyze_figma.py
│   │   │   │   │   ├── generate_test_cases.py
│   │   │   │   │   └── combined_analysis.py
│   │   │   │   ├── dto/           # Data Transfer Objects
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── analysis_request.py
│   │   │   │   │   └── analysis_response.py
│   │   │   │   ├── ports/         # Interfaces for infrastructure
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── llm_service.py
│   │   │   │   │   ├── file_storage.py
│   │   │   │   │   └── design_service.py
│   │   │   │   └── services/      # Application orchestration
│   │   │   │       ├── __init__.py
│   │   │   │       └── test_generator_service.py
│   │   │   │
│   │   │   ├── infrastructure/    # 🔧 External integrations
│   │   │   │   ├── adapters/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── anthropic_llm_adapter.py
│   │   │   │   │   ├── figma_api_adapter.py
│   │   │   │   │   ├── local_file_storage_adapter.py
│   │   │   │   │   └── s3_file_storage_adapter.py  # Future
│   │   │   │   ├── repositories/ # Repository implementations
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── prd_repository_impl.py
│   │   │   │   │   └── figma_repository_impl.py
│   │   │   │   ├── config/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── settings.py
│   │   │   │   │   └── dependency_injection.py
│   │   │   │   └── persistence/  # Future: DB layer
│   │   │   │       └── database.py
│   │   │   │
│   │   │   └── presentation/     # 🌐 API layer (FastAPI)
│   │   │       ├── api/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── v1/
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   ├── routes/
│   │   │       │   │   │   ├── __init__.py
│   │   │       │   │   │   ├── analysis.py
│   │   │       │   │   │   ├── figma.py
│   │   │       │   │   │   ├── test_cases.py
│   │   │       │   │   │   └── health.py
│   │   │       │   │   ├── schemas/  # Pydantic models
│   │   │       │   │   │   ├── __init__.py
│   │   │       │   │   │   ├── requests.py
│   │   │       │   │   │   └── responses.py
│   │   │       │   │   └── dependencies/
│   │   │       │   │       ├── __init__.py
│   │   │       │   │       └── auth.py
│   │   │       │   └── middleware/
│   │   │       │       ├── __init__.py
│   │   │       │       ├── cors.py
│   │   │       │       ├── error_handler.py
│   │   │       │       └── logging.py
│   │   │       └── cli/          # CLI interface
│   │   │           ├── __init__.py
│   │   │           └── commands.py
│   │   │
│   │   ├── tests/                 # 🧪 Backend tests (mirrors src structure)
│   │   │   ├── unit/
│   │   │   │   ├── domain/
│   │   │   │   ├── application/
│   │   │   │   └── infrastructure/
│   │   │   ├── integration/
│   │   │   │   ├── api/
│   │   │   │   └── adapters/
│   │   │   ├── e2e/
│   │   │   │   └── workflows/
│   │   │   ├── fixtures/
│   │   │   └── conftest.py
│   │   │
│   │   ├── config/                # Environment configs
│   │   │   ├── .env.development
│   │   │   ├── .env.staging
│   │   │   ├── .env.production
│   │   │   └── .env.example
│   │   │
│   │   ├── scripts/               # Utility scripts
│   │   │   ├── setup.sh
│   │   │   ├── migrate.sh
│   │   │   └── seed_data.py
│   │   │
│   │   ├── docs/                  # Backend-specific docs
│   │   │   ├── api.md
│   │   │   ├── deployment.md
│   │   │   └── troubleshooting.md
│   │   │
│   │   ├── requirements.txt       # Production dependencies
│   │   ├── requirements-dev.txt   # Development dependencies
│   │   ├── Makefile               # Common commands
│   │   ├── pyproject.toml         # Python project config
│   │   ├── Dockerfile             # Container definition
│   │   └── README.md              # Backend README
│   │
│   └── 📦 frontend/               # Frontend service (React + TypeScript)
│       ├── src/
│       │   ├── features/          # Feature-based modules
│       │   │   ├── analysis/
│       │   │   │   ├── components/
│       │   │   │   ├── hooks/
│       │   │   │   ├── services/
│       │   │   │   ├── types/
│       │   │   │   └── tests/
│       │   │   ├── figma/
│       │   │   └── testCases/
│       │   ├── shared/            # Shared utilities
│       │   │   ├── components/
│       │   │   ├── hooks/
│       │   │   ├── utils/
│       │   │   └── types/
│       │   ├── api/               # API client layer
│       │   │   ├── client.ts
│       │   │   ├── endpoints/
│       │   │   └── types/
│       │   ├── App.tsx
│       │   └── main.tsx
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── e2e/
│       ├── public/
│       ├── .env.development
│       ├── .env.production
│       ├── .env.example
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── Dockerfile
│       └── README.md
│
├── 📂 shared/                     # Shared across packages
│   ├── types/                     # Common TypeScript/Python types
│   └── utils/                     # Common utilities
│
├── 📂 infrastructure/             # Infrastructure as Code
│   ├── terraform/                 # Terraform configs
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── production/
│   │   └── modules/
│   ├── kubernetes/                # K8s manifests
│   │   ├── base/
│   │   └── overlays/
│   ├── docker-compose.yml         # Local development
│   └── README.md
│
├── 📂 .github/                    # GitHub Actions CI/CD
│   ├── workflows/
│   │   ├── backend-ci.yml
│   │   ├── frontend-ci.yml
│   │   ├── deploy-staging.yml
│   │   └── deploy-production.yml
│   └── CODEOWNERS
│
├── 📂 docs/                       # Project-wide documentation
│   ├── ARCHITECTURE.md            # This file
│   ├── CONTRIBUTING.md
│   ├── API_DOCUMENTATION.md
│   ├── DEPLOYMENT.md
│   └── SECURITY.md
│
├── 📂 scripts/                    # Project-wide scripts
│   ├── bootstrap.sh               # Initial setup
│   ├── lint-all.sh                # Run all linters
│   ├── test-all.sh                # Run all tests
│   └── build-all.sh               # Build all packages
│
├── .gitignore                     # Global gitignore
├── .editorconfig                  # Editor configuration
├── Makefile                       # Root-level commands
├── README.md                      # Main README
└── package.json                   # Monorepo workspace config

```

---

## 🎭 Layer Responsibilities

### 1. Domain Layer (Inner Core)
**Purpose**: Pure business logic, completely framework-independent

**Responsibilities**:
- Define business entities (`TestCase`, `PRDDocument`, `FigmaDesign`)
- Implement business rules and validation
- Define repository interfaces (no implementations)
- Domain exceptions

**Rules**:
- ❌ NO framework imports (no FastAPI, no React, no Anthropic SDK)
- ❌ NO infrastructure dependencies
- ✅ Only Python standard library + domain-specific logic
- ✅ 100% testable without external dependencies

**Example**:
```python
# domain/entities/test_case.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class TestCase:
    """Core business entity - completely framework-independent"""
    id: str
    description: str
    priority: Priority  # Value object
    test_type: TestType  # Value object

    def validate(self) -> bool:
        """Business rule: Test must have description"""
        return len(self.description) > 10
```

---

### 2. Application Layer (Use Cases)
**Purpose**: Orchestrates domain logic to fulfill use cases

**Responsibilities**:
- Define use cases (`AnalyzePRDUseCase`, `GenerateTestCasesUseCase`)
- Coordinate domain entities and services
- Define port interfaces for infrastructure
- Application-level validation

**Rules**:
- ✅ Can depend on Domain layer
- ✅ Defines interfaces that Infrastructure implements
- ❌ NO direct infrastructure dependencies
- ✅ Uses dependency injection

**Example**:
```python
# application/use_cases/analyze_prd.py
from domain.entities import PRDDocument, TestChecklist
from application.ports import LLMService, FileStorage

class AnalyzePRDUseCase:
    def __init__(self, llm_service: LLMService, storage: FileStorage):
        self._llm = llm_service  # Interface, not concrete implementation
        self._storage = storage

    def execute(self, request: AnalysisRequest) -> TestChecklist:
        """Business workflow - framework independent"""
        prd = self._storage.load_prd(request.file_path)
        checklist = self._llm.analyze(prd)
        return checklist
```

---

### 3. Infrastructure Layer (Adapters)
**Purpose**: Implements technical details & external integrations

**Responsibilities**:
- Implement repository interfaces
- API adapters (Figma, Anthropic, OpenAI)
- File storage (local, S3, Azure Blob)
- Database access
- Configuration management

**Rules**:
- ✅ Implements interfaces defined in Application layer
- ✅ Can use external libraries (FastAPI, requests, boto3)
- ✅ Handles all technical complexity
- ❌ NO business logic

**Example**:
```python
# infrastructure/adapters/anthropic_llm_adapter.py
from anthropic import Anthropic
from application.ports import LLMService
from domain.entities import PRDDocument, TestChecklist

class AnthropicLLMAdapter(LLMService):
    """Concrete implementation of LLM service"""
    def __init__(self, api_key: str):
        self._client = Anthropic(api_key=api_key)

    def analyze(self, prd: PRDDocument) -> TestChecklist:
        """Technical implementation using Anthropic SDK"""
        response = self._client.messages.create(...)
        return self._parse_response(response)
```

---

### 4. Presentation Layer (UI & API)
**Purpose**: Exposes application to external world

**Responsibilities**:
- FastAPI routes (backend API)
- React components (frontend UI)
- Request/response serialization
- Authentication & authorization
- Error handling & logging

**Rules**:
- ✅ Depends on Application layer
- ✅ Uses dependency injection to get use cases
- ❌ NO direct domain or infrastructure access
- ✅ Thin layer - delegates to use cases

**Example**:
```python
# presentation/api/v1/routes/analysis.py
from fastapi import APIRouter, Depends
from application.use_cases import AnalyzePRDUseCase
from presentation.api.v1.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter()

@router.post("/analyze-prd", response_model=AnalysisResponse)
async def analyze_prd(
    request: AnalysisRequest,
    use_case: AnalyzePRDUseCase = Depends(get_analyze_prd_use_case)
):
    """Thin API layer - delegates to use case"""
    result = use_case.execute(request)
    return AnalysisResponse.from_domain(result)
```

---

## 📊 Data Flow

```
User Request (HTTP/CLI)
        ↓
[Presentation Layer]
  - Validates request
  - Creates DTO
        ↓
[Application Layer]
  - Executes use case
  - Orchestrates domain
        ↓
[Domain Layer]
  - Applies business rules
  - Validates entities
        ↓
[Infrastructure Layer]
  - Calls external APIs
  - Persists data
        ↓
Response flows back up through layers
```

---

## 🔧 Environment Configuration

### Configuration Loading Priority
1. Environment variables (highest priority)
2. `.env.{environment}` files
3. `.env` file
4. Default values in code (lowest priority)

### Environment Files

```bash
# .env.example (Template)
APP_NAME=prd-test-generator
APP_ENV=development
LOG_LEVEL=INFO

# API Keys (use secret management in production)
ANTHROPIC_API_KEY=your_key_here
FIGMA_API_TOKEN=your_token_here

# Infrastructure
FILE_STORAGE_TYPE=local  # local | s3 | azure
FILE_STORAGE_PATH=./storage

# Database (future)
DATABASE_URL=postgresql://localhost:5432/testgen

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

### Secrets Management

**Development**: `.env.development` (git-ignored)
**Staging/Production**: Use secret managers
- AWS: AWS Secrets Manager / Parameter Store
- GCP: Google Secret Manager
- Azure: Azure Key Vault
- Generic: HashiCorp Vault

---

## 🧪 Testing Strategy

### Test Organization (Mirrors Source Structure)

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── domain/             # Domain logic tests
│   ├── application/        # Use case tests
│   └── infrastructure/     # Adapter tests
├── integration/            # Tests with real dependencies
│   ├── api/               # API integration tests
│   └── adapters/          # Adapter integration tests
└── e2e/                   # End-to-end workflows
    └── workflows/
```

### Test Types

| Type | Scope | Speed | When to Use |
|------|-------|-------|-------------|
| **Unit** | Single class/function | Very Fast | All business logic, domain entities |
| **Integration** | Multiple components | Medium | API endpoints, database access |
| **E2E** | Full workflow | Slow | Critical user journeys |

### Testing Pyramid

```
       /\
      /E2E\      <- Few (10%)
     /------\
    /  Integ \   <- Some (30%)
   /----------\
  /    Unit    \ <- Many (60%)
 /--------------\
```

### Example Test Structure

```python
# tests/unit/domain/entities/test_test_case.py
def test_test_case_validation():
    """Unit test - no external dependencies"""
    test_case = TestCase(
        id="TC001",
        description="Short",  # Too short
        priority=Priority.P0,
        test_type=TestType.POSITIVE
    )
    assert not test_case.validate()

# tests/integration/api/test_analysis_endpoint.py
@pytest.mark.integration
def test_analyze_prd_endpoint(test_client, mock_llm):
    """Integration test - real API, mocked external services"""
    response = test_client.post("/api/v1/analyze-prd", files={...})
    assert response.status_code == 200

# tests/e2e/workflows/test_complete_analysis.py
@pytest.mark.e2e
def test_complete_prd_to_test_cases_workflow(test_client):
    """E2E test - real workflow, real services (or staging)"""
    # Upload PRD -> Analyze -> Generate Tests -> Download
    ...
```

---

## 🚀 CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/backend-ci.yml
name: Backend CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
      - name: Install dependencies
        run: make install
      - name: Lint
        run: make lint
      - name: Unit tests
        run: make test-unit
      - name: Integration tests
        run: make test-integration
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t prd-test-gen:${{ github.sha }} .
      - name: Push to registry
        run: docker push ...
```

---

## 📈 Scalability Patterns

### Monorepo → Microservices Migration Path

**Current (Monorepo)**:
```
packages/
├── backend/    # Single deployment
└── frontend/   # Single deployment
```

**Future (Microservices)**:
```
services/
├── analysis-service/      # PRD & Figma analysis
├── test-generation-service/  # Test case generation
├── llm-service/            # LLM abstraction layer
├── storage-service/        # File storage
└── frontend/               # UI
```

### Why This Structure Supports Both:

1. **Clear Module Boundaries**: Each domain module can become a service
2. **Shared Types**: `shared/` package can be npm/pip package
3. **Interface-Based**: All dependencies via ports (easy to make remote)
4. **Stateless Use Cases**: Can be deployed anywhere

### Deployment Options

| Stage | Architecture | Reason |
|-------|--------------|--------|
| **Development** | Monorepo | Fast iteration, simple setup |
| **Small Scale** | Monolith Docker | Cost-effective, simple ops |
| **Medium Scale** | Modular Monolith | Same container, internal modules |
| **Large Scale** | Microservices | Independent scaling, team autonomy |

---

## 🎯 Benefits Summary

### ✅ Framework Independence
- Swap FastAPI for Flask without changing business logic
- Replace Anthropic with OpenAI in one adapter
- Use PostgreSQL or MongoDB with no domain changes

### ✅ Testability
- Domain layer: 100% unit test coverage (no mocks needed)
- Application layer: Mock only infrastructure
- Infrastructure: Test against real/staging APIs

### ✅ Scalability
- Start as monorepo, split to microservices when needed
- Each module can be deployed independently
- Horizontal scaling at service level

### ✅ Maintainability
- Clear responsibilities (single-responsibility principle)
- Easy to find code (consistent structure)
- New developers onboard faster

### ✅ CI/CD Friendly
- Independent test suites
- Docker-ready from day one
- Environment-specific configs

---

## 📚 Next Steps

1. **Immediate**: Restructure following this architecture
2. **Short-term**: Add CI/CD pipelines
3. **Medium-term**: Add database layer, caching
4. **Long-term**: Consider microservices if scale requires

---

**Maintainer**: Development Team
**Review Schedule**: Quarterly
**Questions**: Open GitHub issue or contact architecture team
