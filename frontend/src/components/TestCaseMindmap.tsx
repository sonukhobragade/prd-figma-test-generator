import { useEffect, useRef } from 'react';
import { Transformer } from 'markmap-lib';
import { Markmap } from 'markmap-view';
import { Toolbar } from 'markmap-toolbar';
import 'markmap-toolbar/dist/style.css';

interface TestCaseMindmapProps {
  markdown: string;
}

export function TestCaseMindmap({ markdown }: TestCaseMindmapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const markmapRef = useRef<Markmap | null>(null);

  useEffect(() => {
    if (!svgRef.current || !markdown) {
      console.log('🗺️ Mindmap: Missing SVG ref or markdown', { hasSvg: !!svgRef.current, hasMarkdown: !!markdown, markdownLength: markdown?.length });
      return;
    }

    console.log('🗺️ Mindmap: Rendering with markdown', { length: markdown.length, preview: markdown.substring(0, 100) });

    try {
      // Transform markdown to markmap data
      const transformer = new Transformer();
      const { root } = transformer.transform(markdown);

      console.log('🗺️ Mindmap: Transformed data', { root });

      // Create or update markmap
      if (!markmapRef.current) {
        console.log('🗺️ Mindmap: Creating new Markmap instance');
        markmapRef.current = Markmap.create(svgRef.current, {
          color: (node: unknown) => {
            // Custom colors based on depth
            const colors = [
              '#8b5cf6', // Purple for root
              '#6366f1', // Indigo for level 1
              '#3b82f6', // Blue for level 2
              '#10b981', // Green for level 3
              '#f59e0b', // Amber for level 4
            ];
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            return colors[(node as any).depth] || '#6b7280';
          },
          paddingX: 16,
          duration: 500,
          maxWidth: 300,
        } as any);

        // Add toolbar
        Toolbar.create(markmapRef.current);
        console.log('🗺️ Mindmap: Toolbar created');
      }

      // Render the mindmap
      markmapRef.current.setData(root);
      markmapRef.current.fit();
      console.log('🗺️ Mindmap: Data set and fitted');

    } catch (error) {
      console.error('🗺️ Mindmap: Error rendering', error);
    }

    return () => {
      // Don't destroy on every re-render, only when component unmounts
    };
  }, [markdown]);

  // Cleanup only on unmount
  useEffect(() => {
    return () => {
      if (markmapRef.current) {
        console.log('🗺️ Mindmap: Destroying instance');
        markmapRef.current.destroy();
        markmapRef.current = null;
      }
    };
  }, []);

  return (
    <div className="relative w-full bg-white rounded-lg shadow-sm border border-gray-200" style={{ height: '600px' }}>
      <svg
        ref={svgRef}
        className="w-full h-full"
      />
    </div>
  );
}
