'use client';

import { useState, ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TabItem {
  id: string;
  label: string;
  icon: ReactNode;
}

interface TabGroupProps {
  label: string;
  icon: ReactNode;
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  defaultExpanded?: boolean;
}

export function TabGroup({
  label,
  icon,
  tabs,
  activeTab,
  onTabChange,
  defaultExpanded = false,
}: TabGroupProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const hasActiveTab = tabs.some(tab => tab.id === activeTab);

  return (
    <div className="relative">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap',
          hasActiveTab
            ? 'bg-background text-foreground border-b-2 border-primary'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
        )}
      >
        {icon}
        <span>{label}</span>
        {isExpanded ? (
          <ChevronDown className="h-3 w-3 ml-1" />
        ) : (
          <ChevronRight className="h-3 w-3 ml-1" />
        )}
      </button>

      {isExpanded && (
        <div className="absolute top-full left-0 z-50 mt-1 min-w-[160px] bg-background border rounded-lg shadow-lg py-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                onTabChange(tab.id);
                setIsExpanded(false);
              }}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors',
                activeTab === tab.id
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  children: ReactNode;
}

export function TabButton({ active, onClick, icon, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap',
        active
          ? 'bg-background text-foreground border-b-2 border-primary'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
      )}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}

export default TabGroup;
