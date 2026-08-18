# PRD Test Case Generator - Frontend

React + TypeScript + Vite + Tremor + Tailwind CSS

## Development

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Features

- **PRD Upload**: Drag & drop PRD files (PDF, PNG, JPG, JPEG)
- **Figma Import**: Import designs from Figma URLs
- **Test Case Table**: Sortable, filterable test cases with CSV export
- **Analytics**: Real-time stats (total cases, P0/P1 counts, coverage score)

## Backend

The frontend proxies API requests to the FastAPI backend running on port 8000.

Make sure to start the backend server first:

```bash
# From project root
cd ..
source venv/bin/activate
python app.py
```
