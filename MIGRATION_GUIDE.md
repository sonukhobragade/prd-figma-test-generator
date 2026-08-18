# Migration Guide: Flat Structure → Clean Architecture

> **Goal**: Restructure project from flat structure to clean architecture
> **Impact**: High - Requires code reorganization and import updates
> **Duration**: 2-4 hours
> **Risk**: Medium - Thorough testing required

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Migration Strategy](#migration-strategy)
3. [Step-by-Step Guide](#step-by-step-guide)
4. [Automated Migration Script](#automated-migration-script)
5. [Manual Adjustments](#manual-adjustments)
6. [Testing](#testing)
7. [Rollback Plan](#rollback-plan)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Prerequisites

### Before You Start

- [ ] **Backup**: Create full git branch backup
- [ ] **Clean State**: Ensure no uncommitted changes
- [ ] **Tests Pass**: All existing tests passing
- [ ] **Dependencies**: All dependencies installed
- [ ] **Documentation**: Read ARCHITECTURE.md

```bash
# Create backup branch
git checkout -b backup/pre-clean-architecture-$(date +%Y%m%d)
git push origin backup/pre-clean-architecture-$(date +%Y%m%d)

# Create working branch
git checkout main
git checkout -b feat/clean-architecture-migration

# Verify tests pass
pytest tests/ -v
```

---

## 🗺️ Migration Strategy

### Phase 1: Preparation (30 min)
1. Create new directory structure
2. Set up empty module files with `__init__.py`
3. Configure environment files

### Phase 2: Domain Layer Migration (1 hour)
1. Move models → domain/entities
2. Extract business logic → domain/services
3. Update imports

### Phase 3: Application Layer Migration (1 hour)
1. Extract use cases from app.py
2. Create port interfaces
3. Set up DTOs

### Phase 4: Infrastructure Layer Migration (1 hour)
1. Move API clients → adapters
2. Implement repositories
3. Configure dependency injection

### Phase 5: Presentation Layer Migration (30 min)
1. Restructure FastAPI routes
2. Update schemas
3. Configure middleware

### Phase 6: Testing & Validation (1 hour)
1. Update test imports
2. Run full test suite
3. Manual smoke testing

---

## 🚀 Step-by-Step Guide

### Step 1: Create New Structure

```bash
# Run automated structure creation script
python scripts/create_clean_architecture_structure.py

# Or manually:
mkdir -p packages/backend/src/{domain,application,infrastructure,presentation}
mkdir -p packages/backend/src/domain/{entities,value_objects,repositories,services,exceptions}
mkdir -p packages/backend/src/application/{use_cases,dto,ports,services}
mkdir -p packages/backend/src/infrastructure/{adapters,repositories,config,persistence}
mkdir -p packages/backend/src/presentation/api/v1/{routes,schemas,dependencies,middleware}
mkdir -p packages/backend/{tests,config,scripts,docs}
mkdir -p packages/backend/tests/{unit,integration,e2e}
```

### Step 2: Move Domain Entities

**From**: `framework/models.py`
**To**: `packages/backend/src/domain/entities/`

```bash
# Create entity files
touch packages/backend/src/domain/entities/{__init__.py,test_case.py,prd_document.py,figma_design.py,test_checklist.py}

# Copy relevant classes
# From framework/models.py → domain/entities/test_case.py
```

**Example Migration**:

```python
# OLD: framework/models.py
from pydantic import BaseModel

class TestCase(BaseModel):
    id: str
    description: str
    priority: str
    test_type: str

# NEW: domain/entities/test_case.py
from dataclasses import dataclass
from domain.value_objects import Priority, TestType

@dataclass(frozen=True)
class TestCase:
    """Domain entity - pure business logic"""
    id: str
    description: str
    priority: Priority  # Value object
    test_type: TestType  # Value object

    def validate(self) -> bool:
        """Business rule validation"""
        return len(self.description) > 10 and self.priority.is_valid()
```

### Step 3: Extract Value Objects

```bash
touch packages/backend/src/domain/value_objects/{__init__.py,priority.py,test_type.py}
```

```python
# domain/value_objects/priority.py
from enum import Enum

class Priority(Enum):
    """Priority value object"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    def is_critical(self) -> bool:
        return self == Priority.P0

    def is_valid(self) -> bool:
        return self in Priority
```

### Step 4: Create Repository Interfaces

```bash
touch packages/backend/src/domain/repositories/{__init__.py,prd_repository.py}
```

```python
# domain/repositories/prd_repository.py
from abc import ABC, abstractmethod
from pathlib import Path
from domain.entities import PRDDocument

class PRDRepository(ABC):
    """Interface for PRD storage - no implementation details"""

    @abstractmethod
    def save(self, prd: PRDDocument) -> Path:
        """Save PRD and return file path"""
        pass

    @abstractmethod
    def load(self, file_path: Path) -> PRDDocument:
        """Load PRD from file path"""
        pass
```

### Step 5: Create Use Cases

```bash
touch packages/backend/src/application/use_cases/{__init__.py,analyze_prd.py}
```

```python
# application/use_cases/analyze_prd.py
from domain.entities import PRDDocument, TestChecklist
from application.ports import LLMService, FileStorage
from application.dto import AnalysisRequest, AnalysisResponse

class AnalyzePRDUseCase:
    """Use case for analyzing PRD - orchestrates domain logic"""

    def __init__(self, llm_service: LLMService, storage: FileStorage):
        self._llm = llm_service  # Dependency injection via interface
        self._storage = storage

    def execute(self, request: AnalysisRequest) -> AnalysisResponse:
        """Execute use case"""
        # 1. Load PRD
        prd = self._storage.load_prd(request.file_path)

        # 2. Validate (domain rule)
        if not prd.is_valid():
            raise ValueError("Invalid PRD document")

        # 3. Analyze via LLM
        checklist = self._llm.analyze_prd(prd)

        # 4. Save results
        saved_path = self._storage.save_checklist(checklist)

        # 5. Return response
        return AnalysisResponse(
            checklist=checklist,
            saved_path=saved_path
        )
```

### Step 6: Implement Adapters

```bash
touch packages/backend/src/infrastructure/adapters/{__init__.py,anthropic_llm_adapter.py,figma_api_adapter.py}
```

```python
# infrastructure/adapters/anthropic_llm_adapter.py
from anthropic import Anthropic
from application.ports import LLMService
from domain.entities import PRDDocument, TestChecklist

class AnthropicLLMAdapter(LLMService):
    """Concrete implementation of LLM service using Anthropic"""

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def analyze_prd(self, prd: PRDDocument) -> TestChecklist:
        """Implement LLM analysis using Anthropic SDK"""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"Analyze this PRD: {prd.content}"
            }]
        )

        # Parse response and return domain entity
        return self._parse_response(response)

    def _parse_response(self, response) -> TestChecklist:
        """Convert API response to domain entity"""
        # Implementation details
        ...
```

### Step 7: Restructure API Routes

```bash
touch packages/backend/src/presentation/api/v1/routes/{__init__.py,analysis.py}
```

```python
# presentation/api/v1/routes/analysis.py
from fastapi import APIRouter, Depends, File, UploadFile
from application.use_cases import AnalyzePRDUseCase
from presentation.api.v1.schemas import AnalysisRequest, AnalysisResponse
from infrastructure.config.dependency_injection import get_analyze_prd_use_case

router = APIRouter(prefix="/api/v1/analysis", tags=["Analysis"])

@router.post("/prd", response_model=AnalysisResponse)
async def analyze_prd(
    file: UploadFile = File(...),
    feature_name: str = None,
    use_case: AnalyzePRDUseCase = Depends(get_analyze_prd_use_case)
):
    """Thin API layer - delegates to use case"""
    request = AnalysisRequest(file=file, feature_name=feature_name)
    result = use_case.execute(request)
    return AnalysisResponse.from_domain(result)
```

### Step 8: Set Up Dependency Injection

```python
# infrastructure/config/dependency_injection.py
from functools import lru_cache
from application.use_cases import AnalyzePRDUseCase
from infrastructure.adapters import AnthropicLLMAdapter, LocalFileStorageAdapter
from infrastructure.config.settings import get_settings

@lru_cache()
def get_llm_adapter():
    """Get LLM adapter singleton"""
    settings = get_settings()
    return AnthropicLLMAdapter(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL
    )

@lru_cache()
def get_file_storage():
    """Get file storage adapter singleton"""
    settings = get_settings()
    return LocalFileStorageAdapter(storage_path=settings.FILE_STORAGE_PATH)

def get_analyze_prd_use_case():
    """Factory for AnalyzePRDUseCase"""
    return AnalyzePRDUseCase(
        llm_service=get_llm_adapter(),
        storage=get_file_storage()
    )
```

### Step 9: Update Tests

```bash
# Move and restructure tests
mkdir -p packages/backend/tests/unit/domain/entities
mkdir -p packages/backend/tests/unit/application/use_cases
mkdir -p packages/backend/tests/integration/adapters

# Move tests
mv tests/test_models.py packages/backend/tests/unit/domain/entities/test_test_case.py
mv tests/test_figma_client.py packages/backend/tests/integration/adapters/test_figma_adapter.py
```

**Update imports**:

```python
# OLD
from framework.models import TestCase

# NEW
from domain.entities import TestCase
```

---

## 🤖 Automated Migration Script

Save this script as `scripts/migrate_to_clean_architecture.py`:

```python
#!/usr/bin/env python3
"""Automated migration script for clean architecture restructure."""

import shutil
from pathlib import Path

# Define mappings
MAPPINGS = {
    # Framework models → Domain entities
    "framework/models.py": "packages/backend/src/domain/entities/",

    # Framework utils → Infrastructure/Application
    "framework/utils.py": "packages/backend/src/infrastructure/config/",

    # Framework clients → Infrastructure adapters
    "framework/figma_client.py": "packages/backend/src/infrastructure/adapters/figma_api_adapter.py",
    "framework/llm_analyzer.py": "packages/backend/src/infrastructure/adapters/anthropic_llm_adapter.py",
    "framework/prd_uploader.py": "packages/backend/src/infrastructure/adapters/file_storage_adapter.py",

    # App → Presentation
    "app.py": "packages/backend/src/presentation/api/main.py",

    # CLI → Presentation
    "cli.py": "packages/backend/src/presentation/cli/commands.py",

    # Tests
    "tests/": "packages/backend/tests/",
}

def create_structure():
    """Create new directory structure"""
    dirs = [
        "packages/backend/src/domain/entities",
        "packages/backend/src/domain/value_objects",
        "packages/backend/src/domain/repositories",
        "packages/backend/src/domain/services",
        "packages/backend/src/application/use_cases",
        "packages/backend/src/application/dto",
        "packages/backend/src/application/ports",
        "packages/backend/src/infrastructure/adapters",
        "packages/backend/src/infrastructure/repositories",
        "packages/backend/src/infrastructure/config",
        "packages/backend/src/presentation/api/v1/routes",
        "packages/backend/src/presentation/api/v1/schemas",
        "packages/backend/tests/unit/domain",
        "packages/backend/tests/unit/application",
        "packages/backend/tests/integration",
        "packages/backend/tests/e2e",
    ]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        # Create __init__.py files
        (Path(dir_path) / "__init__.py").touch()

    print("✅ Directory structure created")

def migrate_files():
    """Migrate files to new locations"""
    for old_path, new_path in MAPPINGS.items():
        old = Path(old_path)
        new = Path(new_path)

        if old.exists():
            if old.is_file():
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, new)
                print(f"✅ Migrated: {old} → {new}")
            elif old.is_dir():
                shutil.copytree(old, new, dirs_exist_ok=True)
                print(f"✅ Migrated: {old}/ → {new}/")
        else:
            print(f"⚠️  Not found: {old}")

def update_imports():
    """Update import statements (placeholder - manual review needed)"""
    print("\n⚠️  MANUAL STEP REQUIRED:")
    print("Update all import statements from:")
    print("  from framework.models import ... → from domain.entities import ...")
    print("  from framework.figma_client import ... → from infrastructure.adapters import ...")

if __name__ == "__main__":
    print("🚀 Starting migration to clean architecture...\n")

    create_structure()
    migrate_files()
    update_imports()

    print("\n✅ Migration complete!")
    print("\n📋 Next steps:")
    print("1. Manually split models.py into separate entity files")
    print("2. Extract use cases from app.py")
    print("3. Create port interfaces in application/ports/")
    print("4. Update all import statements")
    print("5. Run tests: pytest packages/backend/tests/")
    print("6. Review and commit changes")
```

**Run script**:

```bash
python scripts/migrate_to_clean_architecture.py
```

---

## ✋ Manual Adjustments

After running automated script, perform these manual steps:

### 1. Split models.py into Entities

```bash
# Edit domain/entities/test_case.py
# Edit domain/entities/prd_document.py
# Edit domain/entities/figma_design.py
# etc.
```

### 2. Extract Use Cases from app.py

Review each endpoint in `app.py` and extract business logic into use cases.

### 3. Create Port Interfaces

```python
# application/ports/llm_service.py
from abc import ABC, abstractmethod

class LLMService(ABC):
    @abstractmethod
    def analyze_prd(self, prd: PRDDocument) -> TestChecklist:
        pass
```

### 4. Update All Imports

Use find-replace or IDE refactoring:

```bash
# Find all occurrences
rg "from framework" packages/backend/

# Replace manually or with sed
find packages/backend -name "*.py" -exec sed -i 's/from framework.models/from domain.entities/g' {} \;
```

---

## 🧪 Testing

### Run Test Suite

```bash
# All tests
pytest packages/backend/tests/ -v

# By layer
pytest packages/backend/tests/unit/domain/ -v
pytest packages/backend/tests/unit/application/ -v
pytest packages/backend/tests/integration/ -v

# Coverage
pytest packages/backend/tests/ --cov=packages/backend/src --cov-report=html
```

### Manual Smoke Testing

1. Start backend: `cd packages/backend && uvicorn src.presentation.api.main:app --reload`
2. Test endpoints:
   - `GET /health` → Should return 200
   - `POST /api/v1/analysis/prd` → Upload test PRD
   - `POST /api/v1/analysis/figma` → Test Figma URL

### Validate Structure

```bash
# Check all __init__.py files exist
find packages/backend/src -type d -exec test -e {}/__init__.py \; -print

# Check no circular imports
python -c "from packages.backend.src.domain import entities; print('✅ No circular imports')"

# Verify tests pass
pytest packages/backend/tests/ --tb=short
```

---

## ⏪ Rollback Plan

If migration fails or issues arise:

```bash
# 1. Checkout backup branch
git checkout backup/pre-clean-architecture-YYYYMMDD

# 2. Or revert commits
git log --oneline  # Find migration commits
git revert <commit-hash>

# 3. Or hard reset (DANGER - loses uncommitted work)
git reset --hard origin/main
```

---

## 🔧 Troubleshooting

### Issue: Import errors after migration

```python
# Error: ModuleNotFoundError: No module named 'framework'

# Solution: Update PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/packages/backend/src"

# Or in pytest.ini:
[pytest]
pythonpath = packages/backend/src
```

### Issue: Circular imports

```
# Error: ImportError: cannot import name 'X' from partially initialized module

# Solution: Move interface to separate file
# Instead of:
# domain/entities/test_case.py imports domain/services/validator.py
# domain/services/validator.py imports domain/entities/test_case.py

# Do:
# Create domain/interfaces/validator.py with interface
# domain/services/validator_impl.py implements interface
```

### Issue: Tests fail after migration

```bash
# Check test discovery
pytest --collect-only packages/backend/tests/

# Update conftest.py paths
# Update fixture imports

# Run with verbose output
pytest packages/backend/tests/ -vv --tb=short
```

---

## 📊 Migration Checklist

- [ ] **Phase 1: Preparation**
  - [ ] Create backup branch
  - [ ] All tests passing
  - [ ] Clean working directory

- [ ] **Phase 2: Structure Creation**
  - [ ] New directory structure created
  - [ ] All `__init__.py` files in place
  - [ ] Configuration files copied

- [ ] **Phase 3: Domain Migration**
  - [ ] Entities separated from models.py
  - [ ] Value objects extracted
  - [ ] Repository interfaces defined
  - [ ] Domain services extracted

- [ ] **Phase 4: Application Migration**
  - [ ] Use cases extracted from app.py
  - [ ] Port interfaces created
  - [ ] DTOs defined

- [ ] **Phase 5: Infrastructure Migration**
  - [ ] Adapters implement ports
  - [ ] Repositories implemented
  - [ ] Dependency injection configured

- [ ] **Phase 6: Presentation Migration**
  - [ ] API routes restructured
  - [ ] Schemas updated
  - [ ] Middleware configured

- [ ] **Phase 7: Testing**
  - [ ] All tests migrated
  - [ ] Imports updated
  - [ ] Tests passing
  - [ ] Coverage maintained

- [ ] **Phase 8: Documentation**
  - [ ] README updated
  - [ ] ARCHITECTURE.md reviewed
  - [ ] API docs regenerated
  - [ ] Team notified

---

## ✅ Success Criteria

Migration is complete when:

1. ✅ All tests passing (119+ tests)
2. ✅ Code coverage maintained (>75%)
3. ✅ No framework imports in domain layer
4. ✅ API endpoints working as before
5. ✅ CI/CD pipeline passing
6. ✅ Documentation updated
7. ✅ Team trained on new structure

---

## 📞 Support

If you encounter issues:

1. Check [ARCHITECTURE.md](./ARCHITECTURE.md) for structure details
2. Review [Troubleshooting](#troubleshooting) section
3. Open GitHub issue with `migration` label
4. Contact architecture team

---

**Good luck with the migration! 🚀**
