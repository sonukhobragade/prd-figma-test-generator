import { useState } from 'react';
import { Sparkles, Database, PlusCircle, Github, Settings, Bug } from 'lucide-react';
import { StreamingDemo } from './components/StreamingDemo';
import { TestRepository } from './components/TestRepository';
import { ZKConfigPanel } from './components/ZKConfigPanel';
import { BugsKnowledge } from './components/BugsKnowledge';
import { Button } from '@/components/ui/button';

type Tab = 'generate' | 'repository' | 'zkconfig' | 'bugs';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('generate');

  return (
    <div className="min-h-screen bg-background">
      {/* Header with Navigation */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-background/95 border-b border-border/50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-18 py-3">
            {/* Logo and Brand */}
            <div className="flex items-center space-x-3">
              <div
                className="flex items-center justify-center w-11 h-11 rounded-xl bg-primary shadow-lg ring-2 ring-primary/20"
                style={{ backgroundColor: "hsl(var(--primary))" }}
              >
                <Sparkles className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground tracking-tight">
                  TestGen AI
                </h1>
                <p className="text-xs text-muted-foreground font-medium">
                  PRD to Test Cases Generator
                </p>
              </div>
            </div>

            {/* Tab Navigation */}
            <nav className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg">
              <button
                onClick={() => setActiveTab('generate')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'generate'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                <PlusCircle className="h-4 w-4" />
                Generate Tests
              </button>
              <button
                onClick={() => setActiveTab('repository')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'repository'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                <Database className="h-4 w-4" />
                Test Repository
              </button>
              <button
                onClick={() => setActiveTab('zkconfig')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'zkconfig'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                <Settings className="h-4 w-4" />
                ZK Config
              </button>
              <button
                onClick={() => setActiveTab('bugs')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'bugs'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                <Bug className="h-4 w-4" />
                Learn from Bugs
              </button>
            </nav>

            {/* Right Actions */}
            <div className="flex items-center space-x-3">
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="h-4 w-4" />
                <span className="hidden sm:inline">GitHub</span>
              </a>
              <Button variant="default" className="hidden sm:flex shadow-md hover:shadow-lg transition-shadow">
                Get Started
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Content - Keep all tabs mounted to preserve state */}
      <div className={activeTab === 'generate' ? 'block' : 'hidden'}>
        <StreamingDemo />
      </div>
      <div className={activeTab === 'repository' ? 'block' : 'hidden'}>
        <TestRepository />
      </div>
      <div className={activeTab === 'zkconfig' ? 'block' : 'hidden'}>
        <ZKConfigPanel />
      </div>
      <div className={activeTab === 'bugs' ? 'block' : 'hidden'}>
        <BugsKnowledge />
      </div>
    </div>
  );
}

export default App;
