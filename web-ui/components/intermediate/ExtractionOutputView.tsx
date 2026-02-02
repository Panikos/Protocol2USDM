'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  FileJson, 
  Copy, 
  Check,
  ChevronDown,
  ChevronRight,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ExtractionOutputViewProps {
  data: Record<string, unknown> | null;
  title?: string;
}

export function ExtractionOutputView({ data, title = 'Extraction Output' }: ExtractionOutputViewProps) {
  const [copied, setCopied] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set(['root']));

  if (!data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileJson className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No extraction data available</p>
        </CardContent>
      </Card>
    );
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleExpand = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const expandAll = () => {
    const allKeys = new Set<string>();
    const collectKeys = (obj: unknown, prefix: string) => {
      if (obj && typeof obj === 'object') {
        allKeys.add(prefix);
        if (Array.isArray(obj)) {
          obj.forEach((item, i) => collectKeys(item, `${prefix}[${i}]`));
        } else {
          Object.entries(obj).forEach(([key, value]) => {
            collectKeys(value, `${prefix}.${key}`);
          });
        }
      }
    };
    collectKeys(data, 'root');
    setExpandedKeys(allKeys);
  };

  const collapseAll = () => {
    setExpandedKeys(new Set(['root']));
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileJson className="h-5 w-5" />
            {title}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={expandAll}>
              Expand All
            </Button>
            <Button variant="outline" size="sm" onClick={collapseAll}>
              Collapse
            </Button>
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        
        {/* Search */}
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search keys or values..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border rounded-md bg-background"
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="font-mono text-sm bg-muted rounded-lg p-4 max-h-[600px] overflow-auto">
          <JsonTreeNode 
            data={data} 
            path="root" 
            expandedKeys={expandedKeys} 
            toggleExpand={toggleExpand}
            searchTerm={searchTerm.toLowerCase()}
            depth={0}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function JsonTreeNode({
  data,
  path,
  expandedKeys,
  toggleExpand,
  searchTerm,
  depth,
}: {
  data: unknown;
  path: string;
  expandedKeys: Set<string>;
  toggleExpand: (key: string) => void;
  searchTerm: string;
  depth: number;
}) {
  const isExpanded = expandedKeys.has(path);
  const indent = depth * 16;

  if (data === null) {
    return <span className="text-gray-500">null</span>;
  }

  if (data === undefined) {
    return <span className="text-gray-500">undefined</span>;
  }

  if (typeof data === 'boolean') {
    return <span className="text-purple-600">{data.toString()}</span>;
  }

  if (typeof data === 'number') {
    return <span className="text-blue-600">{data}</span>;
  }

  if (typeof data === 'string') {
    const isMatch = searchTerm && data.toLowerCase().includes(searchTerm);
    return (
      <span className={cn('text-green-600', isMatch && 'bg-yellow-200')}>
        "{data}"
      </span>
    );
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="text-gray-500">[]</span>;
    }

    return (
      <div>
        <button
          onClick={() => toggleExpand(path)}
          className="inline-flex items-center hover:bg-muted-foreground/10 rounded px-1"
        >
          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span className="text-gray-500">Array({data.length})</span>
        </button>
        {isExpanded && (
          <div style={{ marginLeft: indent }}>
            {data.map((item, i) => (
              <div key={i} className="flex">
                <span className="text-gray-400 mr-2">{i}:</span>
                <JsonTreeNode
                  data={item}
                  path={`${path}[${i}]`}
                  expandedKeys={expandedKeys}
                  toggleExpand={toggleExpand}
                  searchTerm={searchTerm}
                  depth={depth + 1}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data);
    if (entries.length === 0) {
      return <span className="text-gray-500">{'{}'}</span>;
    }

    return (
      <div>
        <button
          onClick={() => toggleExpand(path)}
          className="inline-flex items-center hover:bg-muted-foreground/10 rounded px-1"
        >
          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span className="text-gray-500">Object({entries.length})</span>
        </button>
        {isExpanded && (
          <div style={{ marginLeft: indent }}>
            {entries.map(([key, value]) => {
              const isKeyMatch = searchTerm && key.toLowerCase().includes(searchTerm);
              return (
                <div key={key} className="flex">
                  <span className={cn('text-red-600 mr-2', isKeyMatch && 'bg-yellow-200')}>
                    "{key}":
                  </span>
                  <JsonTreeNode
                    data={value}
                    path={`${path}.${key}`}
                    expandedKeys={expandedKeys}
                    toggleExpand={toggleExpand}
                    searchTerm={searchTerm}
                    depth={depth + 1}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return <span>{String(data)}</span>;
}

export default ExtractionOutputView;
