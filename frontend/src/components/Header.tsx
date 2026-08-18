import { Sparkles, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Header() {
  return (
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

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-8">
            <a
              href="#features"
              className="text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors relative group"
            >
              Features
              <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-primary transition-all group-hover:w-full"></span>
            </a>
            <a
              href="#docs"
              className="text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors relative group"
            >
              Documentation
              <span className="absolute bottom-0 left-0 w-0 h-0.5 bg-primary transition-all group-hover:w-full"></span>
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
            >
              <Github className="h-4 w-4" />
              <span>GitHub</span>
            </a>
          </nav>

          {/* CTA Button */}
          <div className="flex items-center space-x-3">
            <Button variant="default" className="hidden sm:flex shadow-md hover:shadow-lg transition-shadow">
              Get Started
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
